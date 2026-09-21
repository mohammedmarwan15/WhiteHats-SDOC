import sys
from pathlib import Path
import streamlit as st

st.write("✅ Step 1: Streamlit itself works")

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "pipeline"))

st.write("✅ Step 2: About to import classify.py")
from classify import classify_email
st.write("✅ Step 3: classify.py imported fine")

st.write("✅ Step 4: About to import decide.py")
import decide as decide_module
decide_module.ATTACH_ROOT = ROOT / "data"
from decide import evaluate_comparison_email
st.write("✅ Step 5: decide.py imported fine — everything works!")