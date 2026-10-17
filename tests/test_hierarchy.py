from wimbl.agents.hierarchy import family_for, inheritance_chain, official_domain

def test_football_family():
    assert family_for("football trip") == "football"
    assert family_for("Champions League night in Madrid") == "football"
    assert inheritance_chain("football") == ["global", "sports", "football"]

def test_non_football_goal_falls_back_to_sports():
    assert family_for("tennis") == "sports"

def test_official_domain_matches_hostname_not_substring():
    assert official_domain("https://www.fcbarcelona.com/en/tickets", "football") == "fcbarcelona.com"
    assert official_domain("https://fcbarcelona.com.tickets-cheap.example/", "football") is None
