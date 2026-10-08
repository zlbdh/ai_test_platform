"""
Contract testing service.

Supports API contract testing:
- Provider verification
- Consumer-driven contracts
- Contract version management
- Pact format compatibility
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import json
import hashlib
from datetime import datetime
import aiohttp
import asyncio


class ContractStatus(Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass
class ContractInteraction:
    """Contract interaction"""
    description: str
    request: Dict[str, Any]
    response: Dict[str, Any]


@dataclass 
class Contract:
    """API contract"""
    contract_id: str
    consumer: str
    provider: str
    interactions: List[ContractInteraction]
    version: str
    created_at: str
    status: ContractStatus


@dataclass
class VerificationResult:
    """Verification result"""
    contract_id: str
    passed: bool
    total_interactions: int
    passed_interactions: int
    failed_interactions: int
    failures: List[Dict[str, Any]]
    verification_time_ms: int


class ContractTestingService:
    """Contract testing service"""
    
    def __init__(self):
        self.contracts: Dict[str, Contract] = {}
        self.verification_history: List[VerificationResult] = []
    
    def _generate_id(self, consumer: str, provider: str) -> str:
        """Generate a contract ID"""
        content = f"{consumer}:{provider}:{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def create_contract(
        self,
        consumer: str,
        provider: str,
        interactions: List[Dict[str, Any]],
        version: str = "1.0.0"
    ) -> Contract:
        """Create a contract"""
        contract_id = self._generate_id(consumer, provider)
        
        parsed_interactions = [
            ContractInteraction(
                description=i.get("description", ""),
                request=i.get("request", {}),
                response=i.get("response", {})
            )
            for i in interactions
        ]
        
        contract = Contract(
            contract_id=contract_id,
            consumer=consumer,
            provider=provider,
            interactions=parsed_interactions,
            version=version,
            created_at=datetime.now().isoformat(),
            status=ContractStatus.PENDING
        )
        
        self.contracts[contract_id] = contract
        return contract
    
    async def verify_contract(
        self,
        contract_id: str,
        provider_base_url: str
    ) -> VerificationResult:
        """Verify a contract"""
        contract = self.contracts.get(contract_id)
        if not contract:
            return VerificationResult(
                contract_id=contract_id,
                passed=False,
                total_interactions=0,
                passed_interactions=0,
                failed_interactions=1,
                failures=[{"error": "Contract not found"}],
                verification_time_ms=0
            )
        
        start_time = datetime.now()
        failures = []
        passed_count = 0
        
        async with aiohttp.ClientSession() as session:
            for interaction in contract.interactions:
                result = await self._verify_interaction(
                    session,
                    provider_base_url,
                    interaction
                )
                
                if result["passed"]:
                    passed_count += 1
                else:
                    failures.append({
                        "description": interaction.description,
                        "error": result.get("error"),
                        "expected": result.get("expected"),
                        "actual": result.get("actual")
                    })
        
        elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
        total = len(contract.interactions)
        
        passed = passed_count == total
        contract.status = ContractStatus.VERIFIED if passed else ContractStatus.FAILED
        
        result = VerificationResult(
            contract_id=contract_id,
            passed=passed,
            total_interactions=total,
            passed_interactions=passed_count,
            failed_interactions=total - passed_count,
            failures=failures,
            verification_time_ms=elapsed
        )
        
        self.verification_history.append(result)
        return result
    
    async def _verify_interaction(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        interaction: ContractInteraction
    ) -> Dict[str, Any]:
        """Verify a single interaction"""
        request = interaction.request
        expected = interaction.response
        
        url = base_url + request.get("path", "/")
        method = request.get("method", "GET").upper()
        headers = request.get("headers", {})
        body = request.get("body")
        
        try:
            async with session.request(
                method,
                url,
                headers=headers,
                json=body if body else None,
                ssl=False
            ) as response:
                actual_status = response.status
                actual_body = await response.json() if response.content_type == "application/json" else await response.text()
                
                # Verify the status code
                expected_status = expected.get("status", 200)
                if actual_status != expected_status:
                    return {
                        "passed": False,
                        "error": "Status code mismatch",
                        "expected": expected_status,
                        "actual": actual_status
                    }
                
                # Verify the response body by checking key fields
                expected_body = expected.get("body", {})
                if expected_body:
                    for key, exp_value in expected_body.items():
                        if isinstance(actual_body, dict):
                            actual_value = actual_body.get(key)
                            if actual_value != exp_value:
                                return {
                                    "passed": False,
                                    "error": f"Body mismatch at '{key}'",
                                    "expected": exp_value,
                                    "actual": actual_value
                                }
                
                return {"passed": True}
        
        except Exception as e:
            return {
                "passed": False,
                "error": str(e)
            }
    
    def export_pact(self, contract_id: str) -> Dict[str, Any]:
        """Export in Pact format"""
        contract = self.contracts.get(contract_id)
        if not contract:
            return {}
        
        return {
            "consumer": {"name": contract.consumer},
            "provider": {"name": contract.provider},
            "interactions": [
                {
                    "description": i.description,
                    "request": i.request,
                    "response": i.response
                }
                for i in contract.interactions
            ],
            "metadata": {
                "pactSpecification": {"version": "2.0.0"}
            }
        }
    
    def import_pact(self, pact_data: Dict[str, Any]) -> Contract:
        """Import a Pact contract"""
        consumer = pact_data.get("consumer", {}).get("name", "unknown")
        provider = pact_data.get("provider", {}).get("name", "unknown")
        interactions = pact_data.get("interactions", [])
        
        return self.create_contract(consumer, provider, interactions)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics"""
        total = len(self.contracts)
        verified = sum(1 for c in self.contracts.values() if c.status == ContractStatus.VERIFIED)
        failed = sum(1 for c in self.contracts.values() if c.status == ContractStatus.FAILED)
        
        return {
            "total_contracts": total,
            "verified": verified,
            "failed": failed,
            "pending": total - verified - failed,
            "verification_runs": len(self.verification_history)
        }


# Singleton
_contract_service: Optional[ContractTestingService] = None

def get_contract_service() -> ContractTestingService:
    """Get the contract testing service"""
    global _contract_service
    if _contract_service is None:
        _contract_service = ContractTestingService()
    return _contract_service
