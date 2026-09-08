from app.services.ocr import OCRLine, OCRResult, extract_cnh_name_candidate, extract_name_candidate


def test_extracts_cnh_holder_name_below_label():
    ocr = OCRResult(
        text=(
            "CARTEIRA NACIONAL DE HABILITACAO / DRIVER LICENSE\n"
            "2e 1 NOME E SOBRENOME 1a HABILITACAO\n"
            "NOME SOCIAL TESTE CENTO E DEZ\n"
            "24/05/2022\n"
            "3 DATA LOCAL E UF DE NASCIMENTO"
        ),
        lines=[
            OCRLine("CARTEIRA NACIONAL DE HABILITACAO / DRIVER LICENSE", 85),
            OCRLine("2e 1 NOME E SOBRENOME 1a HABILITACAO", 88),
            OCRLine("NOME SOCIAL TESTE CENTO E DEZ", 93),
            OCRLine("24/05/2022", 95),
            OCRLine("3 DATA LOCAL E UF DE NASCIMENTO", 91),
        ],
    )

    assert extract_cnh_name_candidate(ocr) == "NOME SOCIAL TESTE CENTO E DEZ"


def test_rejects_date_as_name():
    ocr = OCRResult(
        text="NOME\nSOCIAL TESTE CENTO E DEZ 24/05/2022",
        lines=[
            OCRLine("NOME", 90),
            OCRLine("SOCIAL TESTE CENTO E DEZ 24/05/2022", 88),
        ],
    )

    assert extract_name_candidate(ocr) is None


def test_field_label_is_not_selected_as_name():
    ocr = OCRResult(
        text="DATA LOCAL E UF DE NASCIMENTO\nCARLOS EDUARDO SILVA",
        lines=[
            OCRLine("DATA LOCAL E UF DE NASCIMENTO", 96),
            OCRLine("CARLOS EDUARDO SILVA", 90),
        ],
    )

    assert extract_name_candidate(ocr) == "CARLOS EDUARDO SILVA"
