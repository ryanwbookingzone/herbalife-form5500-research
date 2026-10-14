from form5500 import brokers

def test_aliases():
    assert brokers.group("PETER C. FOY & ASSOCIATES") == "PCF / Trucordia (Peter C. Foy)"
    assert brokers.group("PCF INSURANCE SERVICES OF THE WEST") == "PCF / Trucordia (Peter C. Foy)"
    assert brokers.group("HUB INTL INSURANCE SERVICES") == "HUB International"
    assert brokers.group("GALLAGHER BENEFIT SERVICES, INC.") == "Gallagher"
    assert brokers.group("TBG DANCO INSURANCE SERVICES CORP") == "TBG Danco"

def test_aon_word_boundary():
    assert brokers.group("MAONE AGENCY") != "Aon"

def test_suffix_stripping():
    assert brokers.group("Acme Benefits Group, LLC") == brokers.group("ACME INSURANCE SERVICES INC")
