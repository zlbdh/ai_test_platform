import json
import hashlib
import logging
import re
import time as _time
from typing import List, Dict, Any, Tuple
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from core.llm_manager import get_llm_for_role
from core.config import Config
from services.knowledge import kb
from core.prompts import (
    SCENARIO_DISCOVERY_PROMPT,
    STEP_GENERATION_PROMPT,
    SMART_PLAN_PROMPT,
    SEMANTIC_VERIFY_PROMPT,
    MULTIMODAL_VERIFY_PROMPT,
)
from core.execution_profile import (
    PROBE_EXECUTION_MODE,
    build_probe_goal_hint,
    resolve_execution_profile,
)

logger = logging.getLogger(__name__)
get_llm = get_llm_for_role

class TestGenerationService:
    """
    智能测试生成服务
    基于 RAG (PRD + Schema) 自动生成测试计划
    """
    # ── LLM 调用缓存（避免相同需求重复调用）──
    _plan_cache: Dict[str, Tuple[float, Dict]] = {}   # {hash: (timestamp, result)}
    CACHE_TTL = 300  # 5 分钟过期
    CACHE_VERSION = "v3"

    async def generate_plan(
        self,
        requirement: str,
        enable_rag: bool = True,
        target_url: str = "",
        execution_mode: str = "default",
        interaction_policy: str = "default",
    ) -> Dict[str, Any]:
        """
        生成测试计划入口 (Async)
        """
        if not requirement or not requirement.strip():
            return {"requirement": requirement, "sources": [], "test_cases": [], "error": "Requirement cannot be empty"}

        execution_profile = resolve_execution_profile(
            requirement=requirement,
            execution_mode=execution_mode,
            interaction_policy=interaction_policy,
        )

        # ── 缓存检查 ──
        cache_key = hashlib.md5(
            (
                f"{self.CACHE_VERSION}|{requirement}|{enable_rag}|{target_url}|"
                f"{execution_profile['execution_mode']}|{execution_profile['interaction_policy']}"
            ).encode()
        ).hexdigest()
        cached = self._plan_cache.get(cache_key)
        if cached:
            ts, result = cached
            if _time.time() - ts < self.CACHE_TTL:
                logger.info(f"Plan cache HIT (key={cache_key[:8]}..., age={_time.time()-ts:.0f}s)")
                return result
            else:
                del self._plan_cache[cache_key]  # 过期清除

        if execution_profile["execution_mode"] == PROBE_EXECUTION_MODE:
            result = self._generate_probe_plan(requirement=requirement, target_url=target_url)
            self._plan_cache[cache_key] = (_time.time(), result)
            logger.info("Probe plan generated locally (target=%s)", target_url or "N/A")
            return result
        # 1. 知识检索
        import time
        import asyncio
        t0 = time.time()
        context = ""
        sources = []
        if enable_rag:
            # 尝试初始化知识库（懒加载）
            # kb.initialize() is sync, run in thread if heavy, but usually fast enough if already init
            kb.initialize()
            
        if enable_rag and kb.enabled:
            logger.info(f"Retrieving knowledge for: {requirement}")
            # 检索 PRD 和 Schema
            try:
                # 增强 RAG: 使用 similarity_search_with_score 获取相关性分数
                raw_results = await asyncio.to_thread(
                    kb.vector_store.similarity_search_with_score, requirement, k=8
                )
                
                # 相关性过滤: 丢弃 score 低于阈值的文档
                # 注意: 不同向量存储的 score 含义不同
                # Chroma: 距离越小越好 (L2), 阈值设为 1.5
                # FAISS: 距离越小越好
                RELEVANCE_THRESHOLD = 1.5
                filtered = [(doc, score) for doc, score in raw_results if score < RELEVANCE_THRESHOLD]
                
                # 按相关性排序 (score 越小 = 越相关)
                filtered.sort(key=lambda x: x[1])
                
                # 去重: 基于 page_content hash 去重
                seen_hashes = set()
                unique_results = []
                for doc, score in filtered:
                    content_hash = hash(doc.page_content[:200])
                    if content_hash not in seen_hashes:
                        seen_hashes.add(content_hash)
                        unique_results.append((doc, score))
                
                # 限制最终取 top-5
                top_results = unique_results[:5]
                
                context_parts = []
                for doc, score in top_results:
                    meta = doc.metadata
                    source_name = meta.get('filename', 'Unknown')
                    relevance_pct = max(0, (1 - score / RELEVANCE_THRESHOLD)) * 100
                    
                    context_parts.append(
                        f"--- 来源: {source_name} (相关度: {relevance_pct:.0f}%) ---\n"
                        f"{doc.page_content}\n"
                    )
                    sources.append(source_name)
                
                # 限制总 context 长度 (防止超出 LLM token 限制)
                context = "\n".join(context_parts)
                if len(context) > 8000:
                    context = context[:8000] + "\n...(已截断)"
                
                logger.info(
                    f"RAG Enhanced: {len(raw_results)} retrieved → "
                    f"{len(filtered)} after filter → {len(top_results)} after dedup "
                    f"(Time: {time.time()-t0:.2f}s)"
                )
            except Exception as e:
                logger.error(f"RAG retrieval failed: {e}")
        else:
            logger.info("RAG not enabled or skipped")
            
        # 2. 链路零：侦察兵 (Crawl-First)
        # 如果提供了 URL，先派侦察兵去看看真实情况
        page_context = ""
        scout_result: Dict[str, Any] = {}
        if target_url:
            from agents.scout_agent import ScoutAgent
            logger.info(f"🕵️ Dispatching Scout to: {target_url}")
            try:
                # Scout is async
                scout_result = await ScoutAgent.scout(target_url)
                if scout_result.get('status') == 'success':
                    page_context = (
                        f"\n【真实页面状态 (由 Scout Agent 实时探测)】\n"
                        f"Title: {scout_result.get('title', 'Unknown')}\n"
                        f"Visible Text Summary: {scout_result.get('visible_text', '')[:500]}...\n"
                        f"Interactive Elements (关键): {scout_result.get('interactive_summary', '')}\n"
                        f"----------------------------------------\n"
                    )
                    logger.info(f"Scout returned successful report. Title: {scout_result.get('title')}")
                else:
                    logger.warning(f"Scout failed: {scout_result.get('message')}")
            except Exception as e:
                logger.error(f"Scout execution error: {e}")
        
        # 3. 链路路由：智能路由 (Smart Router)
        from services.context_analyzer import ContextAnalyzer
        router_result = ContextAnalyzer.analyze(requirement, target_url, context)
        strategy = router_result['strategy']
        logger.info(f"🎯 Smart Router Decision: {strategy} | Reason: {router_result['reasoning']}")
        
        # 4. 链路一：场景挖掘 (Scenario Discovery)
        t1 = time.time()
        # 将 Scout 的发现注入到 Context 中
        full_context = page_context + "\n" + context
        scenarios = await self._discover_scenarios(requirement, full_context, target_url)
        logger.info(f"Scenario Discovery finished (Time: {time.time()-t1:.2f}s)")
        
        # 5. 链路二：步骤生成 (Step Generation) - 并行执行
        t2 = time.time()
        test_cases = []
        priority_counts = {"P0": 0, "P1": 0, "P2": 0}
        dimensions_covered = set()
        
        # Create coroutines for each scenario
        tasks = []
        for scenario in scenarios:
            tasks.append(self._generate_steps_for_scenario(scenario, context, target_url))
            
        # Execute in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for idx, res in enumerate(results):
            scenario = scenarios[idx]
            if isinstance(res, Exception):
                logger.error(f"Step generation error for scenario '{scenario['name']}': {res}")
                steps = self._build_fallback_steps(
                    requirement=requirement,
                    scenario=scenario,
                    target_url=target_url,
                    scout_result=scout_result,
                )
                if not steps:
                    continue
                logger.warning(f"Scenario '{scenario['name']}' 使用本地 fallback 步骤继续执行")
            else:
                steps = res

            if not steps:
                steps = self._build_fallback_steps(
                    requirement=requirement,
                    scenario=scenario,
                    target_url=target_url,
                    scout_result=scout_result,
                )
                if not steps:
                    logger.warning(f"Scenario '{scenario['name']}' 未生成有效步骤，已跳过")
                    continue
                logger.warning(f"Scenario '{scenario['name']}' 生成空步骤，已切换为本地 fallback")

            steps = self._prune_redundant_authenticated_login_steps(requirement, target_url, steps)
            steps = self._prune_redundant_site_selection_steps(requirement, target_url, steps)

            priority = scenario.get('priority', 'P1')
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            if scenario.get('dimension'):
                dimensions_covered.add(scenario['dimension'])
            test_cases.append({
                "scenario": scenario['name'],
                "description": scenario['description'],
                "priority": priority,
                "precondition": scenario.get('precondition', ''),
                "test_data": scenario.get('test_data', []),
                "steps": steps
            })
        
        logger.info(f"Total Plan Generation Time: {time.time()-t0:.2f}s (Parallelized)")
            
        result = {
            "requirement": requirement,
            "sources": list(set(sources)),
            "test_cases": test_cases,
            "coverage_summary": {
                "total_scenarios": len(test_cases),
                "by_priority": priority_counts,
                "dimensions_covered": list(dimensions_covered)
            }
        }

        # ── 缓存写入 ──
        self._plan_cache[cache_key] = (_time.time(), result)
        logger.info(f"Plan cache STORE (key={cache_key[:8]}..., cases={len(test_cases)})")
        return result

    @staticmethod
    def _generate_probe_plan(requirement: str, target_url: str = "") -> Dict[str, Any]:
        steps: List[Dict[str, Any]] = []
        if target_url:
            steps.append({"action": "goto", "target": target_url, "value": ""})
        steps.append({"action": "wait", "target": "1", "value": ""})
        steps.append({"action": "screenshot", "target": "probe_snapshot", "value": ""})

        return {
            "requirement": requirement,
            "sources": [],
            "test_cases": [
                {
                    "scenario": "只读探针验证",
                    "description": "只验证页面可访问性与首屏可见性，不执行登录、输入或提交",
                    "priority": "P0",
                    "precondition": "",
                    "test_data": [],
                    "steps": steps,
                }
            ],
            "coverage_summary": {
                "total_scenarios": 1,
                "by_priority": {"P0": 1, "P1": 0, "P2": 0},
                "dimensions_covered": ["只读探针"],
            },
        }

    def _build_fallback_steps(
        self,
        requirement: str,
        scenario: Dict[str, Any],
        target_url: str = "",
        scout_result: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        当 LLM 不可用或返回空步骤时，使用页面侦察结果和需求文本构造最小可执行计划。
        目标不是替代完整 AI 规划，而是保证首页可用性、关键入口和基础渲染至少能被真实验证。
        """
        steps: List[Dict[str, Any]] = []
        service_product_center = self._needs_service_product_center_flow(requirement, target_url)
        if target_url:
            steps.append({"action": "goto", "target": target_url, "value": ""})

        username, password = self._extract_login_credentials(requirement)
        if "重新登录" in requirement:
            steps.append({"action": "click", "target": "重新登录", "value": ""})
        if username:
            steps.append({"action": "fill", "target": "用户名", "value": username})
        if password:
            steps.append({"action": "fill", "target": "密码", "value": password})
        needs_login_flow = any([
            bool(username),
            bool(password),
            "重新登录" in requirement,
            "用户协议" in requirement,
            "我已阅读并同意" in requirement,
        ])

        if "用户协议" in requirement or "我已阅读并同意" in requirement:
            steps.append({"action": "click", "target": "我已阅读并同意用户协议", "value": ""})
        if needs_login_flow and "登录" in requirement:
            steps.append({"action": "click", "target": "登录", "value": ""})
            steps.append({"action": "wait", "target": "2", "value": ""})

        site_targets = [] if self._should_skip_site_selection(requirement, target_url) else self._extract_site_targets(requirement)
        for site_target in site_targets:
            steps.append({"action": "click", "target": site_target, "value": ""})
        if site_targets:
            steps.append({"action": "wait", "target": "2", "value": ""})

        for menu_target in self._extract_menu_targets(requirement):
            steps.append({"action": "click", "target": menu_target, "value": ""})
            steps.append({"action": "wait", "target": "1", "value": ""})

        for label, number in self._extract_metric_assertions(requirement, prefer_ui_labels=service_product_center):
            if service_product_center and label == "待审核":
                continue
            steps.append({"action": "assert", "target": label, "value": ""})
            steps.append({"action": "assert", "target": number, "value": ""})

        search_keyword = self._extract_product_search_keyword(requirement)
        if search_keyword:
            steps.append({"action": "fill", "target": "商品名称", "value": search_keyword})
            steps.append({"action": "click", "target": "搜索", "value": ""})
            steps.append({"action": "assert", "target": search_keyword, "value": ""})
            steps.append({"action": "click", "target": "重置", "value": ""})

        if "SERVICE" in requirement:
            steps.append({"action": "assert", "target": "SERVICE", "value": ""})

        if service_product_center:
            for token in (
                "商品总数",
                "服务商品",
                "上架商品",
                "下架商品",
                "草稿商品",
                "商品名称",
                "商品类型",
                "业务类型",
                "分类",
                "销售价",
                "状态",
                "新增",
                "批量上架",
                "批量下架",
                "批量删除",
                "导出",
                "分类管理",
            ):
                if not any(step["action"] == "assert" and step["target"] == token for step in steps):
                    steps.append({"action": "assert", "target": token, "value": ""})

        if "分类树" in requirement or "分类管理" in requirement or service_product_center:
            steps.append({"action": "click", "target": "分类管理", "value": ""})
            steps.append({"action": "wait", "target": "1", "value": ""})
            for token in ("分类名称", "业务类型", "状态", "新增一级分类"):
                steps.append({"action": "assert", "target": token, "value": ""})

        assertion_target = self._pick_fallback_assertion(requirement, scenario, scout_result or {})
        if assertion_target and not any(
            step["action"] == "assert" and step["target"] == assertion_target for step in steps
        ):
            steps.append({"action": "assert", "target": assertion_target, "value": ""})

        return steps

    @staticmethod
    def _extract_login_credentials(requirement: str) -> Tuple[str, str]:
        user_match = re.search(r"账号\s*([A-Za-z0-9_.@-]+)", requirement)
        password_match = re.search(r"密码\s*([^\s，。,；;]+)", requirement)
        username = user_match.group(1) if user_match else ""
        password = password_match.group(1) if password_match else ""
        return username, password

    @staticmethod
    def _has_authenticated_context(requirement: str, target_url: str = "") -> bool:
        normalized_requirement = TestGenerationService._strip_runtime_hints(requirement or "")
        normalized_target = (target_url or "").lower()
        if not normalized_target:
            return False
        login_like = ("/qylogin", "/login", "login")
        if any(token in normalized_target for token in login_like):
            return False
        authenticated_tokens = ("已登录", "已经登录", "登录态", "预认证", "免登录")
        return any(token in normalized_requirement for token in authenticated_tokens)

    @classmethod
    def _should_skip_site_selection(cls, requirement: str, target_url: str = "") -> bool:
        normalized_requirement = requirement or ""
        station_tokens = ("站点为", "当前站点", "已切换到", "已切站到", "已切换站点到")
        return cls._has_authenticated_context(requirement, target_url) and any(
            token in normalized_requirement for token in station_tokens
        )

    @classmethod
    def _should_skip_login_steps(cls, requirement: str, target_url: str = "") -> bool:
        if not cls._has_authenticated_context(requirement, target_url):
            return False
        normalized_requirement = cls._strip_runtime_hints(requirement or "")
        explicit_login_tokens = (
            "重新登录",
            "退出登录",
            "登录页",
            "登录页面",
            "账号",
            "用户名",
            "密码",
            "验证码",
        )
        return not any(token in normalized_requirement for token in explicit_login_tokens)

    @staticmethod
    def _extract_site_targets(requirement: str) -> List[str]:
        targets: List[str] = []

        def _append_unique(value: str) -> None:
            candidate = (value or "").strip()
            if candidate and candidate not in targets:
                targets.append(candidate)

        for pattern in (
            r"(?:选择|切换到|已切换到|站点为|当前站点(?:是|为)?)\s*([^\s>—\-]+市)",
            r"([^\s>—\-]+市)(?=[-－—])",
        ):
            city_match = re.search(pattern, requirement)
            if city_match:
                _append_unique(city_match.group(1))
                break

        for pattern in (
            r"(?:选择|切换到|已切换到|站点为|当前站点(?:是|为)?)[^\n。；;，,]*?([^\s，。,；;、]+服务站)",
            r"([^\s，。,；;、]+服务站)",
        ):
            station_match = re.search(pattern, requirement)
            if station_match:
                station_name = re.sub(r"^[^\s>—\-]+市[-－—]", "", station_match.group(1)).strip()
                _append_unique(station_name)
                break

        return targets

    def _prune_redundant_site_selection_steps(
        self,
        requirement: str,
        target_url: str,
        steps: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not steps or not self._should_skip_site_selection(requirement, target_url):
            return steps

        site_targets = set(self._extract_site_targets(requirement))
        if not site_targets:
            return steps

        sanitized: List[Dict[str, Any]] = []
        pending_wait_removal = False
        removed = 0

        for step in steps:
            action = str(step.get("action", "")).strip().lower()
            target = str(step.get("target", "")).strip()

            if action == "click" and target in site_targets:
                pending_wait_removal = True
                removed += 1
                continue

            if pending_wait_removal and action == "wait":
                pending_wait_removal = False
                removed += 1
                continue

            pending_wait_removal = False
            sanitized.append(step)

        if removed:
            logger.info(f"Pruned {removed} redundant authenticated site-selection steps")

        return sanitized

    def _prune_redundant_authenticated_login_steps(
        self,
        requirement: str,
        target_url: str,
        steps: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not steps or not self._should_skip_login_steps(requirement, target_url):
            return steps

        login_targets = {
            "重新登录",
            "登录",
            "我已阅读并同意用户协议",
            "用户名",
            "账号",
            "密码",
            "验证码",
        }
        sanitized: List[Dict[str, Any]] = []
        pending_wait_removal = False
        removed = 0

        for step in steps:
            action = str(step.get("action", "")).strip().lower()
            target = str(step.get("target", "")).strip()

            if action in {"click", "fill"} and target in login_targets:
                pending_wait_removal = action == "click" and target in {"重新登录", "登录"}
                removed += 1
                continue

            if pending_wait_removal and action == "wait":
                pending_wait_removal = False
                removed += 1
                continue

            pending_wait_removal = False
            sanitized.append(step)

        if removed:
            logger.info(f"Pruned {removed} redundant authenticated login steps")

        return sanitized

    @staticmethod
    def _extract_menu_targets(requirement: str) -> List[str]:
        menu_match = re.search(r"进入\s*([^\n。；;，,]+?)\s*->\s*([^\n。；;，,]+)", requirement)
        if not menu_match:
            return []
        return [menu_match.group(1).strip(), menu_match.group(2).strip()]

    @staticmethod
    def _extract_metric_assertions(requirement: str, prefer_ui_labels: bool = False) -> List[Tuple[str, str]]:
        metrics: List[Tuple[str, str]] = []
        label_map = {
            "总商品": "商品总数",
            "服务商品": "服务商品",
            "在售": "上架商品",
            "下架": "下架商品",
            "草稿": "草稿商品",
            "待审核": "待审核",
        }
        for label in ("总商品", "服务商品", "在售", "下架", "草稿", "待审核"):
            match = re.search(rf"{label}\s*(\d+)", requirement)
            if match:
                actual_label = label_map[label] if prefer_ui_labels else label
                metrics.append((actual_label, match.group(1)))
        return metrics

    @staticmethod
    def _extract_product_search_keyword(requirement: str) -> str:
        for pattern in (
            r"搜索商品名称\s*([\u4e00-\u9fffA-Za-z0-9_-]{2,40})",
            r"搜索[“\"']([\u4e00-\u9fffA-Za-z0-9_-]{2,40})[”\"']",
        ):
            match = re.search(pattern, requirement)
            if match:
                return match.group(1).strip()
        return ""

    @staticmethod
    def _strip_runtime_hints(requirement: str) -> str:
        sanitized = requirement or ""
        sanitized = re.sub(r"【重要：[^】]*】", "", sanitized)
        sanitized = re.sub(r"【会话预认证已完成：[^】]*】", "", sanitized)
        return sanitized.strip()

    @staticmethod
    def _needs_service_product_center_flow(requirement: str, target_url: str = "") -> bool:
        combined = f"{requirement} {target_url}"
        keywords = ("统一商品服务中心", "服务商品中心", "uniProductService", "unifiedGoodService")
        return any(keyword in combined for keyword in keywords)

    def _pick_fallback_assertion(
        self,
        requirement: str,
        scenario: Dict[str, Any],
        scout_result: Dict[str, Any],
    ) -> str:
        """
        从需求文本和 Scout 侦察结果中提取一个高概率存在于页面中的断言词。
        优先选页面标题这类能被 HTML 精确命中的静态文本，其次才退回登录/注册等 UI 词。
        """
        scenario_name = str(scenario.get("name", ""))
        scenario_desc = str(scenario.get("description", ""))
        title = str(scout_result.get("title", "")).strip()
        visible_text = str(scout_result.get("visible_text", ""))
        interactive_summary = str(scout_result.get("interactive_summary", ""))
        combined = " ".join(
            part for part in [requirement, scenario_name, scenario_desc, visible_text, interactive_summary] if part
        )

        if self._is_reasonable_assertion(title):
            return title

        preferred_tokens = [
            "登录",
            "注册",
            "提交",
            "保存",
            "查询",
            "搜索",
            "确认",
            "用户名",
            "密码",
            "验证码",
            "首页",
            "系统",
            "欢迎",
        ]
        for token in preferred_tokens:
            if token in combined:
                return token

        interactive_matches = re.findall(r"\[[^\]]+\]\s*([^\],]{2,20})", interactive_summary)
        for token in interactive_matches:
            candidate = token.strip()
            if self._is_reasonable_assertion(candidate):
                return candidate

        visible_matches = re.findall(r"[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9_-]{1,15}", visible_text)
        for token in visible_matches:
            candidate = token.strip()
            if self._is_reasonable_assertion(candidate):
                return candidate

        return ""

    @staticmethod
    def _is_reasonable_assertion(candidate: str) -> bool:
        if not candidate:
            return False
        if candidate.startswith("http"):
            return False
        if candidate.isdigit():
            return False
        blocked = {"button", "input", "select", "textarea", "text", "value"}
        return candidate.lower() not in blocked

    async def _discover_scenarios(self, requirement: str, context: str, target_url: str = "") -> List[Dict[str, str]]:
        """
        AI 测试架构师：分析输入 → 决策测什么 (Async)
        """
        url_hint = ""
        if target_url:
            url_hint = f"\n【目标网站】\n{target_url}\n所有测试场景必须围绕该网站的功能展开，不要测试其他无关网站。\n"

        prompt = ChatPromptTemplate.from_template(SCENARIO_DISCOVERY_PROMPT)
        
        try:
            chain = prompt | get_llm_for_role("planner") | JsonOutputParser()
            res = await chain.ainvoke({"requirement": requirement, "context": context, "url_hint": url_hint})
            return res
        except Exception as e:
            logger.warning(f"Scenario discovery failed: {e}")
            return [{"name": "默认场景", "description": "基于需求的基本流程", "priority": "P1", "dimension": "核心业务流程", "precondition": "", "test_data": []}]

    async def _generate_steps_for_scenario(self, scenario: Dict[str, str], context: str, target_url: str = "") -> List[Dict[str, Any]]:
        """
        为单个场景生成执行步骤 (Async Helper)
        """
        import time
        st = time.time()
        steps = await self._generate_steps(scenario, context, target_url)
        logger.info(f"Generated steps for scenario '{scenario['name']}' (Time: {time.time()-st:.2f}s)")
        return steps

    async def _generate_steps(self, scenario: Dict[str, str], context: str, target_url: str = "") -> List[Dict[str, Any]]:
        """
        生成步骤核心逻辑 (Async)
        """
        url_rule = ""
        if target_url:
            url_rule = f"5. 所有 goto 步骤应针对目标网站 {target_url}，不要导航到其他域名。\n"

        prompt = ChatPromptTemplate.from_template(STEP_GENERATION_PROMPT)
        
        try:
            chain = prompt | get_llm_for_role("planner") | JsonOutputParser()
            res = await chain.ainvoke({
                "name": scenario['name'], 
                "description": scenario['description'],
                "context": context,
                "url_rule": url_rule
            })
            return res
        except Exception as e:
            # Re-raise to be caught by gather
            raise e
    async def plan_next_step(
        self,
        goal: str,
        page_state: dict,
        history: list,
        screenshot_b64: str = None,
        execution_profile: Dict[str, Any] | None = None,
    ) -> dict:
        """
        Smart Mode: 单步推理。
        基于目标 + 当前页面状态 + 操作历史，决定下一个动作。
        
        返回: {"thinking": "...", "action": "fill|click|goto|...|done", "target": "...", "value": "..."}
        """
        execution_profile = execution_profile or {}
        prompt_goal = goal
        if execution_profile.get("execution_mode") == PROBE_EXECUTION_MODE:
            prompt_goal = f"{goal}\n{build_probe_goal_hint(page_state.get('url', ''))}"

        # 构建历史摘要（最近 20 步，让 LLM 看到更多重复操作）
        history_text = ""
        loop_warning = ""
        if history:
            recent = history[-20:]
            lines = []
            for i, h in enumerate(recent, 1):
                status_icon = "✅" if h.get('status') == 'success' else "❌"
                lines.append(f"  {i}. {status_icon} {h.get('action', '?')} → {h.get('target', '')} | {h.get('message', '')[:60]}")
            history_text = "\n".join(lines)
            
            # === 死循环检测 ===
            consecutive_same = 1
            if len(history) >= 2:
                last_action = history[-1].get('action', '')
                for h in reversed(history[:-1]):
                    if h.get('action', '') == last_action:
                        consecutive_same += 1
                    else:
                        break
            
            if consecutive_same >= 3:
                last_action = history[-1].get('action', '')
                loop_warning = (
                    f"\n\n【⚠️ 死循环警告！】\n"
                    f"你已经连续执行了 {consecutive_same} 次 '{last_action}' 操作！\n"
                    f"你正在陷入死循环。请立刻停下来，改用其他动作类型。\n"
                )
                if last_action == 'screenshot':
                    loop_warning += (
                        f"screenshot 不会返回图片内容给你 — 你看不到截图内容！\n"
                        f"你必须改用 fill, click, scroll 等实际操作。\n"
                        f"如果是因为验证码卡住了，请直接在验证码输入框填写 '1234' 然后点击登录。\n"
                    )
                logger.warning(f"[SmartPlan] LOOP DETECTED: {consecutive_same}x '{last_action}'")
        else:
            history_text = "  （无，这是第一步）"
        
        # 构建页面状态
        from core.snapshot_compressor import snapshot_compressor
        
        elements_text = page_state.get('interactive_elements', '（页面未加载）')
        snapshot = snapshot_compressor.compress(elements_text, page_state, max_visible_text=200)
        
        prompt = ChatPromptTemplate.from_template(SMART_PLAN_PROMPT)
        
        MAX_RETRIES = 3
        last_error = None
        last_raw_text = ""
        
        # ★ L1: 多模态推理 — 有截图时优先用 VLM
        if screenshot_b64:
            try:
                from core.llm_manager import get_vision_llm
                from langchain_core.messages import HumanMessage
                
                vision_llm = get_vision_llm()
                if vision_llm:
                    prompt_text = SMART_PLAN_PROMPT.format(
                        goal=prompt_goal, snapshot=snapshot,
                        history=history_text, loop_warning=loop_warning,
                    )
                    message = HumanMessage(content=[
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{screenshot_b64}"
                        }},
                    ])
                    raw_response = await vision_llm.ainvoke([message])
                    raw_text = raw_response.content if hasattr(raw_response, 'content') else str(raw_response)
                    logger.info(f"[SmartPlan] ★ Vision mode ({len(raw_text)} chars): {raw_text[:200]}")
                    
                    # 复用 JSON 解析逻辑
                    import re as _re
                    text = raw_text.strip()
                    md_match = _re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, _re.DOTALL)
                    if md_match:
                        text = md_match.group(1).strip()
                    json_start = text.find('{')
                    json_end = text.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        res = json.loads(text[json_start:json_end])
                    else:
                        res = json.loads(text)
                    if 'action' in res:
                        logger.info(f"[SmartPlan] Vision thinking: {res.get('thinking', '?')[:80]}")
                        return res
            except Exception as e:
                logger.warning(f"[SmartPlan] Vision mode failed, fallback to text: {e}")
        
        for attempt in range(MAX_RETRIES):
            try:
                llm = get_llm_for_role("planner")
                # 分步执行: 先获取原始文本，再手动解析 JSON（兼容 markdown 代码块包裹）
                chain = prompt | llm
                raw_response = await chain.ainvoke({
                    "goal": prompt_goal,
                    "snapshot": snapshot,
                    "history": history_text,
                    "loop_warning": loop_warning,
                })
                raw_text = raw_response.content if hasattr(raw_response, 'content') else str(raw_response)
                last_raw_text = raw_text
                logger.info(f"[SmartPlan] LLM raw output (attempt {attempt+1}, {len(raw_text)} chars): {raw_text[:300]}")
                
                # 手动 JSON 解析（兼容 ```json ... ``` 代码块）
                import re as _re
                text = raw_text.strip()
                # 尝试提取 markdown 代码块中的 JSON
                md_match = _re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, _re.DOTALL)
                if md_match:
                    text = md_match.group(1).strip()
                # 提取第一个 { ... } 或直接解析
                json_start = text.find('{')
                json_end = text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    res = json.loads(text[json_start:json_end])
                else:
                    res = json.loads(text)
                
                # 验证必须有 action 字段
                if 'action' not in res:
                    raise ValueError(f"LLM 返回缺少 'action' 字段: {list(res.keys())}")
                
                logger.info(f"[SmartPlan] thinking: {res.get('thinking', '?')[:80]}")
                return res
            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(f"[SmartPlan] Attempt {attempt+1}/{MAX_RETRIES} JSON parse failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    import asyncio as _asyncio
                    await _asyncio.sleep(1)
                    continue
            except Exception as e:
                last_error = e
                logger.warning(f"[SmartPlan] Attempt {attempt+1}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    import asyncio as _asyncio
                    await _asyncio.sleep(1)
                    continue
        
        # 所有重试都失败：智能降级
        logger.error(f"[SmartPlan] All {MAX_RETRIES} attempts failed. Last error: {last_error}")
        logger.error(f"[SmartPlan] Last raw LLM output: {last_raw_text[:500]}")
        
        # 如果是第一步且有 URL，降级为 goto
        target_url = page_state.get('url', '')
        if not history and target_url and target_url != '（未导航）':
            logger.info(f"[SmartPlan] Fallback: goto {target_url}")
            return {"thinking": f"LLM 推理失败（{last_error}），降级为直接打开目标页面", "action": "goto", "target": target_url, "value": ""}
        
        return {"thinking": f"推理失败（重试{MAX_RETRIES}次）: {last_error}", "action": "error", "target": "推理异常终止", "value": ""}

    def semantic_verify(self, assertion: str, page_context: str, screenshot_b64: str = "") -> dict:
        """
        语义验证：LLM 判断页面内容是否满足断言条件。
        当精确文本匹配失败时作为 fallback。
        支持多模态：传入 screenshot_b64 时使用 vision model 联合判断。
        
        返回: {"passed": True/False, "reason": "..."}
        """
        # 解析 page_context 中的 url 和 visible_text
        url = ""
        visible_text = page_context
        if isinstance(page_context, dict):
            url = page_context.get('url', '')
            visible_text = page_context.get('visible_text', '')
        
        # 多模态路径：有截图时使用 vision model
        if screenshot_b64:
            try:
                from core.llm_manager import get_vision_llm
                from langchain_core.messages import HumanMessage

                prompt_text = MULTIMODAL_VERIFY_PROMPT.format(
                    assertion=assertion,
                    url=url,
                    visible_text=str(visible_text)[:2000],
                )
                # 构建多模态消息（文本 + 图片）
                message = HumanMessage(content=[
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
                ])
                vision_llm = get_vision_llm()
                response = vision_llm.invoke([message])
                # 尝试解析 JSON
                import json as _json
                res_text = response.content if hasattr(response, 'content') else str(response)
                # 提取 JSON 部分
                json_start = res_text.find('{')
                json_end = res_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    res = _json.loads(res_text[json_start:json_end])
                    passed = res.get('passed', False)
                    reason = res.get('reason', '无')
                    visual_evidence = res.get('visual_evidence', '')
                    logger.info(f"[MultimodalVerify] {'PASS' if passed else 'FAIL'}: {reason} | visual: {visual_evidence}")
                    return {"passed": passed, "reason": reason, "visual_evidence": visual_evidence}
            except Exception as e:
                logger.warning(f"[MultimodalVerify] Vision model 失败, 降级到文本验证: {e}")
                # 降级到纯文本验证

        # 纯文本路径
        prompt = ChatPromptTemplate.from_template(SEMANTIC_VERIFY_PROMPT)
        try:
            chain = prompt | get_llm_for_role("executor") | JsonOutputParser()
            res = chain.invoke({
                "assertion": assertion,
                "url": url,
                "visible_text": str(visible_text)[:2000],
            })
            passed = res.get('passed', False)
            reason = res.get('reason', '无')
            logger.info(f"[SemanticVerify] {'PASS' if passed else 'FAIL'}: {reason}")
            return {"passed": passed, "reason": reason}
        except Exception as e:
            logger.error(f"[SemanticVerify] LLM call failed: {e}")
            return {"passed": False, "reason": f"语义验证异常: {e}"}

planner_service = TestGenerationService()


