"""Phase 2 test: multi-agent boundary negotiation.

Exercises the full loop: registry -> boundary_scan -> comm negotiation
-> contract record -> registry reconciliation.

Run from the repo root:
    python -m tests.test_phase2
"""
from sova import registry as reg
from sova import comm


def main() -> None:
    # clean mailbox from any prior run
    comm.comm_clear()

    # 1. registry has two agents
    agents = reg.registry_list()
    ids = [a["agent_id"] for a in agents]
    assert "algo-engineer" in ids, "algo-engineer missing"
    assert "backend-engineer" in ids, "backend-engineer missing"
    print(f"[1] registry_list OK -> {ids}")

    # 2. boundary_scan catches the intentional overlap
    scan = reg.boundary_scan()
    assert not scan["clean"], "expected conflicts but got clean"
    llm_conflicts = [c for c in scan["conflicts"]
                     if c["resource"] == "models/llm-gateway"]
    assert llm_conflicts, "no conflict on models/llm-gateway"
    print(f"[2] boundary_scan OK -> {scan['total']} conflict(s):")
    for c in scan["conflicts"]:
        print(f"      {c['type']}  {c.get('agents')}  {c['resource']}")

    # 3. both agents send their case to the other
    comm.comm_send("algo-engineer", "backend-engineer",
                   "model selection and training is my domain; the model layer of llm-gateway should be mine",
                   subject="llm-gateway boundary")
    comm.comm_send("backend-engineer", "algo-engineer",
                   "serving and routing is my domain; the gateway infra should be mine",
                   subject="llm-gateway boundary")
    print("[3] comm_send OK -> both agents stated their case")

    # 4. each agent reads the other's message
    to_algo = comm.comm_read("algo-engineer")
    to_backend = comm.comm_read("backend-engineer")
    assert len(to_algo) == 1 and len(to_backend) == 1
    print(f"[4] comm_read OK -> algo-engineer got: {to_algo[0]['subject']}")

    # 5. record the resolution as a contract
    result = comm.boundary_record(
        "algo-engineer", "backend-engineer",
        contract_body=("Resolved: model selection + training -> algo-engineer.\n"
                       "Serving / routing / infra -> backend-engineer.\n"
                       "API contract defined jointly."),
        summary="llm-gateway boundary split: models=algo, serving=backend")
    assert result["contract_file"]
    print(f"[5] boundary_record OK -> {result['contract_file']}")

    # 6. update registry to reflect the agreed boundary
    reg.registry_update("algo-engineer",
                        owns=["models/recall", "models/ranking", "models/llm-gateway"],
                        intends=[])
    reg.registry_update("backend-engineer",
                        owns=["services/api", "services/search",
                              "services/inference-gateway"],
                        intends=[])
    print("[6] registry_update OK -> boundary reflected in ownership")

    # 7. scan again -> should be clean now
    scan2 = reg.boundary_scan()
    assert scan2["clean"], f"expected clean after resolution, got {scan2}"
    print("[7] boundary_scan after resolution -> CLEAN")

    comm.comm_clear()
    print("\nPHASE 2 GOOD. Multi-agent boundary negotiation works.")
    print("Next: register the MCP server and test switching agents in your CLI.")


if __name__ == "__main__":
    main()
