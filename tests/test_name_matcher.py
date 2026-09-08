from app.services.name_matcher import match_name, normalize_name

def test_normalize_accents():
    assert normalize_name("João da Silva") == "JOAO DA SILVA"

def test_full_name_match():
    result = match_name("João Carlos da Silva", "JOAO CARLOS SILVA")
    assert result["status"] == "match"
    assert result["anchors_ok"] is True

def test_common_first_name_is_not_enough():
    result = match_name("Carlos Eduardo Silva", "Carlos Pereira Souza")
    assert result["status"] != "match"
