import requests
import streamlit as st

def call_api(url, data):
    try:
        response = requests.post(url, json=data, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None