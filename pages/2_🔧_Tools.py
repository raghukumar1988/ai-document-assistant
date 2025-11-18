"""
Tools and Guardrails Testing Page
"""

import streamlit as st
import requests

st.set_page_config(
    page_title="Tools - DocuChat",
    page_icon="🔧",
    layout="wide"
)

API_BASE_URL = st.secrets.get("API_BASE_URL", "http://localhost:8000")

st.title("🔧 Tools & Guardrails")
st.caption("Test agent tools and guardrails")

# Tabs for different tools
tab1, tab2, tab3, tab4 = st.tabs(["🤖 Agent Tools", "🛡️ Input Validation", "🔒 PII Detection", "💰 Token Estimation"])

with tab1:
    st.header("🤖 Agent Tools")
    st.write("Test available tools that the AI agent can use")
    
    # Get available tools
    try:
        response = requests.get(f"{API_BASE_URL}/api/agent/tools")
        if response.status_code == 200:
            tools_data = response.json()
            
            st.metric("Available Tools", len(tools_data.get("tools", [])))
            
            for tool_name in tools_data.get("tools", []):
                description = tools_data.get("descriptions", {}).get(tool_name, "")
                with st.expander(f"🔧 {tool_name}"):
                    st.write(description)
        else:
            st.error("Failed to load tools")
    except Exception as e:
        st.error(f"Error: {str(e)}")
    
    st.divider()
    
    # Test agent
    st.subheader("Test Agent")
    test_query = st.text_input("Enter a query to test the agent", "Calculate 25 * 4")
    
    if st.button("🚀 Run Agent", type="primary"):
        with st.spinner("Agent working..."):
            try:
                response = requests.post(
                    f"{API_BASE_URL}/api/agent/run",
                    json={"query": test_query}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    st.success("✅ Agent completed")
                    
                    # Show output
                    st.write("**Output:**")
                    st.info(result["output"])
                    
                    # Show tools used
                    if result.get("tool_usage"):
                        st.write("**Tools Used:**")
                        for tool in result["tool_usage"]:
                            st.write(f"- **{tool['tool']}**: {tool['tool_input']}")
                            st.caption(f"  Result: {tool['observation'][:200]}...")
                else:
                    st.error("Agent failed")
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")

with tab2:
    st.header("🛡️ Input Validation")
    st.write("Test input validation guardrails")
    
    test_input = st.text_area(
        "Enter text to validate",
        "This is a safe input",
        height=150
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        check_injection = st.checkbox("Check for injection attacks", value=True)
    with col2:
        check_inappropriate = st.checkbox("Check inappropriate content", value=True)
    
    max_length = st.slider("Maximum length", 100, 10000, 1000)
    
    if st.button("✅ Validate Input", type="primary"):
        with st.spinner("Validating..."):
            try:
                response = requests.post(
                    f"{API_BASE_URL}/api/guardrails/validate/input",
                    json={
                        "text": test_input,
                        "max_length": max_length,
                        "check_injection": check_injection,
                        "check_inappropriate": check_inappropriate
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if result.get("valid"):
                        st.success("✅ Input is valid")
                        st.info(result.get("message"))
                    else:
                        st.error("❌ Input is invalid")
                        st.warning(result.get("error"))
                    
                    st.write(f"**Text Length:** {result.get('text_length')} characters")
                else:
                    st.error("Validation failed")
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")
    
    st.divider()
    
    st.subheader("📝 Test Cases")
    
    test_cases = {
        "Valid Input": "What is the capital of France?",
        "XSS Attack": "<script>alert('xss')</script>",
        "SQL Injection": "'; DROP TABLE users; --",
        "Too Long": "a" * 11000
    }
    
    for name, test_text in test_cases.items():
        if st.button(f"Test: {name}"):
            with st.spinner("Testing..."):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/api/guardrails/validate/input",
                        json={"text": test_text, "max_length": 10000}
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("valid"):
                            st.success(f"✅ {name}: Passed")
                        else:
                            st.error(f"❌ {name}: {result.get('error')}")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

with tab3:
    st.header("🔒 PII Detection & Redaction")
    st.write("Detect and redact personally identifiable information")
    
    test_text = st.text_area(
        "Enter text with PII",
        "My email is john.doe@example.com and my phone is 555-123-4567",
        height=150
    )
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔍 Detect PII", use_container_width=True):
            with st.spinner("Detecting..."):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/api/guardrails/pii/detect",
                        json={"text": test_text}
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        if result.get("pii_found"):
                            st.warning(f"⚠️ Found {result['count']} PII entities")
                            
                            st.write("**Types detected:**")
                            for pii_type in result.get("types", []):
                                st.write(f"- {pii_type}")
                        else:
                            st.success("✅ No PII detected")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    
    with col2:
        if st.button("🚫 Redact PII", use_container_width=True):
            with st.spinner("Redacting..."):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/api/guardrails/pii/redact",
                        json={"text": test_text, "mode": "redact"}
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.success("✅ Redacted")
                        st.code(result.get("processed_text"))
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    
    with col3:
        if st.button("🎭 Mask PII", use_container_width=True):
            with st.spinner("Masking..."):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/api/guardrails/pii/redact",
                        json={"text": test_text, "mode": "mask"}
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.success("✅ Masked")
                        st.code(result.get("processed_text"))
                except Exception as e:
                    st.error(f"Error: {str(e)}")

with tab4:
    st.header("💰 Token Estimation")
    st.write("Estimate token count and cost")
    
    test_text = st.text_area(
        "Enter text to estimate",
        "This is a test message to estimate token count and cost",
        height=150
    )
    
    if st.button("📊 Estimate Tokens", type="primary"):
        with st.spinner("Estimating..."):
            try:
                response = requests.post(
                    f"{API_BASE_URL}/api/guardrails/tokens/estimate",
                    json={"text": test_text}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Characters", result.get("text_length"))
                    with col2:
                        st.metric("Estimated Tokens", result.get("estimated_tokens"))
                    with col3:
                        st.metric("Cost (USD)", f"${result.get('cost_estimate_usd', 0):.6f}")
                    
                    if result.get("within_default_limit"):
                        st.success(f"✅ Within limit ({result.get('default_limit')} tokens)")
                    else:
                        st.warning(f"⚠️ Exceeds limit ({result.get('default_limit')} tokens)")
                        
            except Exception as e:
                st.error(f"Error: {str(e)}")