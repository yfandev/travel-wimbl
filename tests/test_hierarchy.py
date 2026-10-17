from wimbl.agents.hierarchy import family_for, inheritance_chain

def test_tennis_family():
    assert family_for("I love tennis") == "tennis"
    assert inheritance_chain("tennis") == ["global", "sports", "tennis"]

def test_football_family():
    assert family_for("football trip") == "football"
