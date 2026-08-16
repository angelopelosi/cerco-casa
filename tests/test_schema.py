import pytest
from scraper.schema import Listing

def make_listing(**overrides):
    base = dict(
        fonte="subito", external_id="123", tipo="affitto",
        titolo="Bilocale centro", prezzo=500, url="https://example.com/123",
    )
    base.update(overrides)
    return Listing(**base)

def test_id_is_deterministic_hash_of_fonte_and_external_id():
    l1 = make_listing()
    l2 = make_listing()
    assert l1.id == l2.id
    assert l1.id != make_listing(external_id="456").id

def test_defaults():
    l = make_listing()
    assert l.categoria == "residenziale"
    assert l.arredato == "non_specificato"
    assert l.superficie_mq is None

def test_validate_accepts_valid_listing():
    make_listing().validate()  # non deve sollevare eccezioni

def test_validate_rejects_bad_tipo():
    with pytest.raises(ValueError):
        make_listing(tipo="ufficio").validate()

def test_validate_rejects_missing_fonte():
    with pytest.raises(ValueError):
        make_listing(fonte="").validate()

def test_validate_rejects_negative_price():
    with pytest.raises(ValueError):
        make_listing(prezzo=-10).validate()
