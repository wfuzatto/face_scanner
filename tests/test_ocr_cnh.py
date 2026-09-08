from app.services.ocr import OCRLine, OCRResult, extract_cnh_name_candidate


def test_extract_cnh_name_with_trailing_date_and_single_letter_particle():
    ocr = OCRResult(
        text="\n".join([
            "2e 1 NOME E SOBRENOME 4º HABILITAÇÃO",
            "| NOME SOCIAL TESTE CENTO E DEZ | | 24/05/2022 |",
            "19/09/1981 SAO PAULO/SP",
        ]),
        lines=[
            OCRLine("2e 1 NOME E SOBRENOME 4º HABILITAÇÃO", 88.0),
            OCRLine("| NOME SOCIAL TESTE CENTO E DEZ | | 24/05/2022 |", 91.0),
            OCRLine("19/09/1981 SAO PAULO/SP", 94.0),
        ],
    )

    assert extract_cnh_name_candidate(ocr) == "NOME SOCIAL TESTE CENTO E DEZ"


def test_extract_cnh_name_ignores_single_noise_character_before_border():
    ocr = OCRResult(
        text="\n".join([
            "2e 1 NOME E SOBRENOME 1º HABIL",
            "p | NOME SOCIAL TESTE CENTO E DEZ | 24/05/2022",
        ]),
        lines=[
            OCRLine("2e 1 NOME E SOBRENOME 1º HABIL", 80.0),
            OCRLine("p | NOME SOCIAL TESTE CENTO E DEZ | 24/05/2022", 86.0),
        ],
    )

    assert extract_cnh_name_candidate(ocr) == "NOME SOCIAL TESTE CENTO E DEZ"
