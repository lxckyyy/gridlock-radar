.PHONY: install demo test check

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

demo:
	.venv/bin/streamlit run app.py

test:
	.venv/bin/pytest -q

check: test
	.venv/bin/python -B -c "import ast; from pathlib import Path; files=[Path('app.py'), *Path('gridlock').rglob('*.py'), *Path('tests').rglob('*.py')]; [ast.parse(p.read_text(), filename=str(p)) for p in files]; print(f'Parsed {len(files)} Python files')"
