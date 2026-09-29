from replay.validator import validate_file


def _write(tmp_path, content: str):
    path = tmp_path / "data.csv"
    path.write_text(content)
    return path


def test_all_valid_records(tmp_path):
    content = (
        "timestamp,symbol,price,quantity,side\n"
        "1,BTCUSD,100.00,10,B\n"
        "2,BTCUSD,100.50,5,S\n"
        "3,ETHUSD,50.00,2,B\n"
    )
    report = validate_file(_write(tmp_path, content))

    assert report.total_records == 3
    assert report.valid_records == 3
    assert report.invalid_records == 0
    assert report.duplicates == 0
    assert report.out_of_order_events == 0
    assert report.missing_values == 0


def test_detects_out_of_order(tmp_path):
    content = (
        "timestamp,symbol,price,quantity,side\n"
        "3,BTCUSD,100.00,10,B\n"
        "1,BTCUSD,100.50,5,S\n"
    )
    report = validate_file(_write(tmp_path, content))
    assert report.out_of_order_events == 1
    assert report.valid_records == 2


def test_detects_duplicates(tmp_path):
    content = (
        "timestamp,symbol,price,quantity,side\n"
        "1,BTCUSD,100.00,10,B\n"
        "1,BTCUSD,100.00,10,B\n"
    )
    report = validate_file(_write(tmp_path, content))
    assert report.duplicates == 1


def test_detects_invalid_price_quantity_side_and_missing(tmp_path):
    content = (
        "timestamp,symbol,price,quantity,side\n"
        "1,BTCUSD,-5.00,10,B\n"
        "2,BTCUSD,100.00,0,S\n"
        "3,BTCUSD,100.00,10,X\n"
        "4,,100.00,10,B\n"
        "5,BTCUSD,abc,10,B\n"
    )
    report = validate_file(_write(tmp_path, content))

    assert report.total_records == 5
    assert report.invalid_records == 5
    assert report.valid_records == 0
    assert report.missing_values == 1
    assert len(report.errors) == 5


def test_detects_malformed_record(tmp_path):
    content = (
        "timestamp,symbol,price,quantity,side\n"
        "1,BTCUSD,100.00,10\n"
    )
    report = validate_file(_write(tmp_path, content))
    assert report.invalid_records == 1
    assert report.errors[0].reason == "malformed record (wrong field count)"
