from main import signal

def test_insufficient_data():
    assert signal([100]*10)["action"] == "WAIT"

def test_output():
    assert signal([100+i for i in range(60)])["action"] in ("BUY","SELL","WAIT")
