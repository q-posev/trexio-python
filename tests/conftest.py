import pytest

def pytest_addoption(parser):
    parser.addoption("--all", action="store_true", help="Run all back-ends")

def pytest_generate_tests(metafunc):
    if "backend" in metafunc.fixturenames:
        metafunc.parametrize("backend",
            ['hdf5','text'] if metafunc.config.getoption("--all") else ['text'])
