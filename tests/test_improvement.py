from wimbl.improvement import evaluate_candidate

def test_full_policy_is_eligible():
    p = {"checks": {k: True for k in ("official_source", "price", "dates", "budget")}}
    assert evaluate_candidate(p)["promotion_decision"] == "eligible_for_review"

def test_weak_policy_rejected():
    p = {"checks": {"official_source": True, "price": False, "dates": False, "budget": False}}
    assert evaluate_candidate(p)["promotion_decision"] == "rejected"
