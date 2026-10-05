#!/usr/bin/env python3
"""Minimal test to verify LangChain callbacks work with LangFuse."""

import os
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)

print("\n" + "="*80)
print("LANGCHAIN CALLBACK TEST")
print("="*80)

# Test 1: Simple model with callback
print("\n[TEST 1] Model.invoke() with config callbacks...")
try:
    from langchain_openai import ChatOpenAI
    from langfuse.integrations.langchain import CallbackHandler

    callback = CallbackHandler()
    print(f"✓ CallbackHandler created: {callback}")

    model = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0.5,
        max_tokens=50,
    )

    # Method 1: with_config
    print(f"\n  Method 1: with_config(callbacks=[...])")
    model_configured = model.with_config(callbacks=[callback])
    response1 = model_configured.invoke("Say 'test1'")
    print(f"  ✓ Got response: {response1.content[:30]}...")

    # Method 2: invoke with config param
    print(f"\n  Method 2: invoke(input, config={{callbacks: [...]}})")
    response2 = model.invoke("Say 'test2'", config={"callbacks": [callback]})
    print(f"  ✓ Got response: {response2.content[:30]}...")

except Exception as e:
    logger.exception("Test 1 failed")

# Test 2: Chain with callback
print("\n[TEST 2] Chain.invoke() with config callbacks...")
try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI
    from langfuse.integrations.langchain import CallbackHandler

    callback = CallbackHandler()

    model = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0.5,
        max_tokens=50,
    )

    prompt = ChatPromptTemplate.from_template("Say '{word}'")
    chain = prompt | model

    # Method 1: with_config on chain
    print(f"\n  Method 1: chain.with_config(callbacks=[...])")
    chain_configured = chain.with_config(callbacks=[callback])
    response1 = chain_configured.invoke({"word": "hello"})
    print(f"  ✓ Got response: {response1.content[:30]}...")

    # Method 2: invoke with config param
    print(f"\n  Method 2: chain.invoke(input, config={{callbacks: [...]}})")
    response2 = chain.invoke({"word": "world"}, config={"callbacks": [callback]})
    print(f"  ✓ Got response: {response2.content[:30]}...")

except Exception as e:
    logger.exception("Test 2 failed")

# Test 3: Flush and verify
print("\n[TEST 3] Flushing and verifying traces...")
try:
    from langfuse import Langfuse
    lf = Langfuse()
    print(f"✓ Langfuse client: {lf}")
    lf.flush()
    print(f"✓ Traces flushed")
except Exception as e:
    logger.exception("Test 3 failed")

print("\n" + "="*80)
print("✓ CALLBACK TESTS COMPLETE")
print("="*80)
print("\nIf all tests passed, check https://us.cloud.langfuse.com")
print("Should see 2-3 traces from this test\n")
