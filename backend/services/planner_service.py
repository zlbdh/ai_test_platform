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
    Intelligent test generation service
    Generate test plans automatically with RAG (PRD + Schema)
    """
    # -- LLM call cache to avoid duplicate calls for identical requirements --
    _plan_cache: Dict[str, Tuple[float, Dict]] = {}   # {hash: (timestamp, result)}
    CACHE_TTL = 300  # Expires after 5 minutes
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
        Generate a test plan asynchronously
        """
        if not requirement or not requirement.strip():
            return {"requirement": requirement, "sources": [], "test_cases": [], "error": "Requirement cannot be empty"}

        execution_profile = resolve_execution_profile(
            requirement=requirement,
            execution_mode=execution_mode,
            interaction_policy=interaction_policy,
        )

        # -- Cache lookup --
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
                del self._plan_cache[cache_key]  # Remove expired entries

        if execution_profile["execution_mode"] == PROBE_EXECUTION_MODE:
            result = self._generate_probe_plan(requirement=requirement, target_url=target_url)
            self._plan_cache[cache_key] = (_time.time(), result)
            logger.info("Probe plan generated locally (target=%s)", target_url or "N/A")
            return result
        # 1. Knowledge retrieval
        import time
        import asyncio
        t0 = time.time()
        context = ""
        sources = []
        if enable_rag:
            # Try to initialize the knowledge service lazily
            # kb.initialize() is sync, run in thread if heavy, but usually fast enough if already init
            kb.initialize()
            
        if enable_rag and kb.enabled:
            logger.info(f"Retrieving knowledge for: {requirement}")
            # Retrieve PRD and Schema
            try:
                # Enhanced RAG: use similarity_search_with_score for relevance scores
                raw_results = await asyncio.to_thread(
                    kb.vector_store.similarity_search_with_score, requirement, k=8
                )
                
                # Relevance filtering: discard documents outside the score threshold
                # Note: score meanings differ between vector stores
                # Chroma: lower L2 distance is better; threshold 1.5
                # FAISS: lower distance is better
                RELEVANCE_THRESHOLD = 1.5
                filtered = [(doc, score) for doc, score in raw_results if score < RELEVANCE_THRESHOLD]
                
                # Sort by relevance: lower score means greater relevance
                filtered.sort(key=lambda x: x[1])
                
                # Deduplicate by page_content hash
                seen_hashes = set()
                unique_results = []
                for doc, score in filtered:
                    content_hash = hash(doc.page_content[:200])
                    if content_hash not in seen_hashes:
                        seen_hashes.add(content_hash)
                        unique_results.append((doc, score))
                
                # Keep at most the top five results
                top_results = unique_results[:5]
                
                context_parts = []
                for doc, score in top_results:
                    meta = doc.metadata
                    source_name = meta.get('filename', 'Unknown')
                    relevance_pct = max(0, (1 - score / RELEVANCE_THRESHOLD)) * 100
                    
                    context_parts.append(
                        f"--- Source: {source_name} (relevance: {relevance_pct:.0f}%) ---\n"
                        f"{doc.page_content}\n"
                    )
                    sources.append(source_name)
                
                # Limit total context length to stay within the LLM token limit
                context = "\n".join(context_parts)
                if len(context) > 8000:
                    context = context[:8000] + "\n...(truncated)"
                
                logger.info(
                    f"RAG Enhanced: {len(raw_results)} retrieved → "
                    f"{len(filtered)} after filter → {len(top_results)} after dedup "
                    f"(Time: {time.time()-t0:.2f}s)"
                )
            except Exception as e:
                logger.error(f"RAG retrieval failed: {e}")
        else:
            logger.info("RAG not enabled or skipped")
            
        # 2. Stage zero: Scout (Crawl-First)
        # If a URL is provided, send the scout to inspect the actual page first
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
                        f"\n[Live page state detected by the Scout Agent]\n"
                        f"Title: {scout_result.get('title', 'Unknown')}\n"
                        f"Visible Text Summary: {scout_result.get('visible_text', '')[:500]}...\n"
                        f"Interactive Elements (key): {scout_result.get('interactive_summary', '')}\n"
                        f"----------------------------------------\n"
                    )
                    logger.info(f"Scout returned successful report. Title: {scout_result.get('title')}")
                else:
                    logger.warning(f"Scout failed: {scout_result.get('message')}")
            except Exception as e:
                logger.error(f"Scout execution error: {e}")
        
        # 3. Routing: Smart Router
        from services.context_analyzer import ContextAnalyzer
        router_result = ContextAnalyzer.analyze(requirement, target_url, context)
        strategy = router_result['strategy']
        logger.info(f"🎯 Smart Router Decision: {strategy} | Reason: {router_result['reasoning']}")
        
        # 4. Stage one: Scenario Discovery
        t1 = time.time()
        # Add Scout findings to the context
        full_context = page_context + "\n" + context
        scenarios = await self._discover_scenarios(requirement, full_context, target_url)
        logger.info(f"Scenario Discovery finished (Time: {time.time()-t1:.2f}s)")
        
        # 5. Stage two: Step Generation in parallel
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
                logger.warning(f"Scenario '{scenario['name']}' will continue with local fallback steps")
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
                    logger.warning(f"Scenario '{scenario['name']}' produced no valid steps and was skipped")
                    continue
                logger.warning(f"Scenario '{scenario['name']}' produced empty steps; using local fallback")

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

        # -- Cache write --
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
                    "scenario": "Read-only Probe Verification",
                    "description": "Check only page accessibility and initial visibility; do not sign in, enter text, or submit",
                    "priority": "P0",
                    "precondition": "",
                    "test_data": [],
                    "steps": steps,
                }
            ],
            "coverage_summary": {
                "total_scenarios": 1,
                "by_priority": {"P0": 1, "P1": 0, "P2": 0},
                "dimensions_covered": ["Read-only Probe"],
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
        When the LLM is unavailable or returns no steps, build a minimal executable plan from scout findings and requirements.
        This supplements full AI planning by ensuring the homepage, critical entry points, and basic rendering can be verified.
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
        Extract assertion text likely to exist on the page from requirements and Scout findings.
        Prefer static text such as the page title that can be matched exactly in HTML, then fall back to UI terms such as sign-in or registration.
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
        AI test architect: analyze inputs and decide what to test asynchronously
        """
        url_hint = ""
        if target_url:
            url_hint = f"\n[Target website]\n{target_url}\nEvery test scenario must address this website's features. Do not test unrelated websites.\n"

        prompt = ChatPromptTemplate.from_template(SCENARIO_DISCOVERY_PROMPT)
        
        try:
            chain = prompt | get_llm_for_role("planner") | JsonOutputParser()
            res = await chain.ainvoke({"requirement": requirement, "context": context, "url_hint": url_hint})
            return res
        except Exception as e:
            logger.warning(f"Scenario discovery failed: {e}")
            return [{"name": "Default Scenario", "description": "Basic requirements-based workflow", "priority": "P1", "dimension": "Core Business Workflow", "precondition": "", "test_data": []}]

    async def _generate_steps_for_scenario(self, scenario: Dict[str, str], context: str, target_url: str = "") -> List[Dict[str, Any]]:
        """
        Generate execution steps for one scenario (async helper)
        """
        import time
        st = time.time()
        steps = await self._generate_steps(scenario, context, target_url)
        logger.info(f"Generated steps for scenario '{scenario['name']}' (Time: {time.time()-st:.2f}s)")
        return steps

    async def _generate_steps(self, scenario: Dict[str, str], context: str, target_url: str = "") -> List[Dict[str, Any]]:
        """
        Core step-generation logic (async)
        """
        url_rule = ""
        if target_url:
            url_rule = f"5. All goto steps must target {target_url}. Do not navigate to other domains.\n"

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
        Smart Mode: reason about one step.
        Choose the next action from the goal, current page state, and action history.
        
        Returns: {"thinking": "...", "action": "fill|click|goto|...|done", "target": "...", "value": "..."}
        """
        execution_profile = execution_profile or {}
        prompt_goal = goal
        if execution_profile.get("execution_mode") == PROBE_EXECUTION_MODE:
            prompt_goal = f"{goal}\n{build_probe_goal_hint(page_state.get('url', ''))}"

        # Summarize the latest 20 steps so the LLM can detect repeated actions
        history_text = ""
        loop_warning = ""
        if history:
            recent = history[-20:]
            lines = []
            for i, h in enumerate(recent, 1):
                status_icon = "✅" if h.get('status') == 'success' else "❌"
                lines.append(f"  {i}. {status_icon} {h.get('action', '?')} → {h.get('target', '')} | {h.get('message', '')[:60]}")
            history_text = "\n".join(lines)
            
            # === Loop detection ===
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
                    f"\n\n[⚠️ Repeated-action loop warning]\n"
                    f"You have executed {consecutive_same} consecutive '{last_action}' actions!\n"
                    f"You are entering a loop. Stop immediately and choose a different action type.\n"
                )
                if last_action == 'screenshot':
                    loop_warning += (
                        f"screenshot does not return image content to you; you cannot see the screenshot!\n"
                        f"Switch to an actual action such as fill, click, or scroll.\n"
                        f"If a verification code is blocking progress, enter '1234' in the verification-code field and click Sign in.\n"
                    )
                logger.warning(f"[SmartPlan] LOOP DETECTED: {consecutive_same}x '{last_action}'")
        else:
            history_text = "  (None; this is the first step)"
        
        # Build the page state
        from core.snapshot_compressor import snapshot_compressor
        
        elements_text = page_state.get('interactive_elements', '(Page not loaded)')
        snapshot = snapshot_compressor.compress(elements_text, page_state, max_visible_text=200)
        
        prompt = ChatPromptTemplate.from_template(SMART_PLAN_PROMPT)
        
        MAX_RETRIES = 3
        last_error = None
        last_raw_text = ""
        
        # L1: Multimodal reasoning; prefer the VLM when a screenshot is available
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
                    
                    # Reuse JSON parsing logic
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
                # Execute in stages: get raw text, then parse JSON manually, supporting Markdown code fences
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
                
                # Parse JSON manually, supporting fenced ```json ... ``` blocks
                import re as _re
                text = raw_text.strip()
                # Try to extract JSON from a Markdown code block
                md_match = _re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, _re.DOTALL)
                if md_match:
                    text = md_match.group(1).strip()
                # Extract the first { ... } object or parse directly
                json_start = text.find('{')
                json_end = text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    res = json.loads(text[json_start:json_end])
                else:
                    res = json.loads(text)
                
                # Require an action field
                if 'action' not in res:
                    raise ValueError(f"LLM response is missing the 'action' field: {list(res.keys())}")
                
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
        
        # All retries failed: controlled fallback
        logger.error(f"[SmartPlan] All {MAX_RETRIES} attempts failed. Last error: {last_error}")
        logger.error(f"[SmartPlan] Last raw LLM output: {last_raw_text[:500]}")
        
        # If this is the first step and a URL exists, fall back to goto
        target_url = page_state.get('url', '')
        if not history and target_url and target_url not in ('(Not navigated)', '（未导航）'):
            logger.info(f"[SmartPlan] Fallback: goto {target_url}")
            return {"thinking": f"LLM reasoning failed ({last_error}); falling back to opening the target page directly", "action": "goto", "target": target_url, "value": ""}
        
        return {"thinking": f"Reasoning failed after {MAX_RETRIES} retries: {last_error}", "action": "error", "target": "Reasoning terminated with an error", "value": ""}

    def semantic_verify(self, assertion: str, page_context: str, screenshot_b64: str = "") -> dict:
        """
        Semantic verification: use the LLM to assess whether page content satisfies an assertion.
        Use as a fallback when exact text matching fails.
        Supports multimodal verification with a vision model when screenshot_b64 is provided.
        
        Returns: {"passed": True/False, "reason": "..."}
        """
        # Parse url and visible_text from page_context
        url = ""
        visible_text = page_context
        if isinstance(page_context, dict):
            url = page_context.get('url', '')
            visible_text = page_context.get('visible_text', '')
        
        # Multimodal path: use the vision model when a screenshot is available
        if screenshot_b64:
            try:
                from core.llm_manager import get_vision_llm
                from langchain_core.messages import HumanMessage

                prompt_text = MULTIMODAL_VERIFY_PROMPT.format(
                    assertion=assertion,
                    url=url,
                    visible_text=str(visible_text)[:2000],
                )
                # Build a multimodal message with text and image
                message = HumanMessage(content=[
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
                ])
                vision_llm = get_vision_llm()
                response = vision_llm.invoke([message])
                # Attempt to parse JSON
                import json as _json
                res_text = response.content if hasattr(response, 'content') else str(response)
                # Extract JSON
                json_start = res_text.find('{')
                json_end = res_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    res = _json.loads(res_text[json_start:json_end])
                    passed = res.get('passed', False)
                    reason = res.get('reason', 'None')
                    visual_evidence = res.get('visual_evidence', '')
                    logger.info(f"[MultimodalVerify] {'PASS' if passed else 'FAIL'}: {reason} | visual: {visual_evidence}")
                    return {"passed": passed, "reason": reason, "visual_evidence": visual_evidence}
            except Exception as e:
                logger.warning(f"[MultimodalVerify] Vision model failed; falling back to text verification: {e}")
                # Fall back to text-only verification

        # Text-only path
        prompt = ChatPromptTemplate.from_template(SEMANTIC_VERIFY_PROMPT)
        try:
            chain = prompt | get_llm_for_role("executor") | JsonOutputParser()
            res = chain.invoke({
                "assertion": assertion,
                "url": url,
                "visible_text": str(visible_text)[:2000],
            })
            passed = res.get('passed', False)
            reason = res.get('reason', 'None')
            logger.info(f"[SemanticVerify] {'PASS' if passed else 'FAIL'}: {reason}")
            return {"passed": passed, "reason": reason}
        except Exception as e:
            logger.error(f"[SemanticVerify] LLM call failed: {e}")
            return {"passed": False, "reason": f"Semantic verification error: {e}"}

planner_service = TestGenerationService()


