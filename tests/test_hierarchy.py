from wimbl.agents.hierarchy import family_for, inheritance_chain, official_domain

def test_football_family():
    assert family_for("football trip") == "football"
    assert family_for("Champions League night in Madrid") == "football"
    assert inheritance_chain("football") == ["global", "sports", "football"]

def test_every_goal_belongs_to_the_football_family():
    # Football-only: goals without a football keyword (club or city names) are still football trips.
    assert family_for("see Barcelona at the Camp Nou in March") == "football"
    assert family_for("tennis") == "football"

def test_official_domain_matches_hostname_not_substring():
    assert official_domain("https://www.fcbarcelona.com/en/tickets", "football") == "fcbarcelona.com"
    assert official_domain("https://fcbarcelona.com.tickets-cheap.example/", "football") is None
