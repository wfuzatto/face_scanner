from app.services.mrz import check_digit, parse_td3

def test_check_digit_reference():
    assert check_digit("L898902C3") == "6"

def test_parse_td3_example():
    text = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\nL898902C36UTO7408122F1204159ZE184226B<<<<<10"
    result = parse_td3(text)
    assert result is not None
    assert result.name == "ANNA MARIA ERIKSSON"
    assert result.document_number == "L898902C3"
    assert result.valid is True
