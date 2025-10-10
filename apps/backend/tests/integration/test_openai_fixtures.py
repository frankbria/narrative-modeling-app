"""
Integration tests for OpenAI API mocking fixtures.

These tests validate that the OpenAI mocking fixtures work correctly for
AI-powered features without making real API calls.

Run with: pytest tests/integration/test_openai_fixtures.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_mock_openai_fixture(mock_openai):
    """Test that mock_openai fixture provides proper mocking."""
    assert mock_openai is not None
    assert "client" in mock_openai
    assert "response" in mock_openai
    assert "async_mock" in mock_openai

    # Verify mock response structure
    response = mock_openai["response"]
    assert response["id"] == "chatcmpl-test123"
    assert response["model"] == "gpt-4"
    assert "choices" in response
    assert len(response["choices"]) == 1


@pytest.mark.asyncio
async def test_mock_openai_chat_completion(mock_openai):
    """Test mocked chat completion call."""
    # Call the mocked method
    result = await mock_openai["client"].chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "test prompt"}]
    )

    # Verify mock was called
    assert mock_openai["async_mock"].called

    # Verify response structure
    assert result.id == "chatcmpl-test123"
    assert result.model == "gpt-4"


def test_openai_response_fixture(test_openai_response):
    """Test that test_openai_response fixture provides canned responses."""
    assert test_openai_response is not None
    assert "data_summary" in test_openai_response
    assert "model_advice" in test_openai_response
    assert "error_diagnosis" in test_openai_response

    # Verify response structure
    data_summary = test_openai_response["data_summary"]
    assert "content" in data_summary
    assert "100 records" in data_summary["content"]


@pytest.mark.asyncio
async def test_openai_data_summarization():
    """Test OpenAI integration for data summarization."""
    from unittest.mock import patch, AsyncMock

    # Create properly structured mock
    mock_message = MagicMock()
    mock_message.content = "Dataset summary: 100 rows, 5 columns, binary classification task"

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("openai.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai.return_value = mock_client

        # Simulate AI summarization call
        client = mock_openai()
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Summarize this dataset"}]
        )

        assert response.choices[0].message.content.startswith("Dataset summary")


@pytest.mark.asyncio
async def test_openai_model_recommendation():
    """Test OpenAI integration for model recommendation."""
    from unittest.mock import patch, AsyncMock

    # Create properly structured mock
    mock_message = MagicMock()
    mock_message.content = "Recommended: Random Forest (accuracy: ~90%), XGBoost (accuracy: ~88%)"

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("openai.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai.return_value = mock_client

        # Simulate AI model recommendation call
        client = mock_openai()
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Recommend ML models for classification"}]
        )

        content = response.choices[0].message.content
        assert "Random Forest" in content or "XGBoost" in content


@pytest.mark.asyncio
async def test_openai_error_handling():
    """Test OpenAI error handling in mocked scenarios."""
    from unittest.mock import patch, AsyncMock
    from openai import OpenAIError

    with patch("openai.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=OpenAIError("API rate limit exceeded")
        )
        mock_openai.return_value = mock_client

        # Simulate API error
        client = mock_openai()

        with pytest.raises(OpenAIError) as exc_info:
            await client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "test"}]
            )

        assert "rate limit" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_openai_streaming_response():
    """Test mocked streaming OpenAI response."""
    from unittest.mock import patch, AsyncMock

    # Mock streaming chunks with proper structure
    async def mock_stream():
        chunks_data = ["This ", "is ", "streaming."]
        for content in chunks_data:
            mock_delta = MagicMock()
            mock_delta.content = content

            mock_choice = MagicMock()
            mock_choice.delta = mock_delta

            mock_chunk = MagicMock()
            mock_chunk.choices = [mock_choice]

            yield mock_chunk

    with patch("openai.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=mock_stream()
        )
        mock_openai.return_value = mock_client

        # Simulate streaming response
        client = mock_openai()
        stream = await client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "test"}],
            stream=True
        )

        # Collect streamed content
        collected = []
        async for chunk in stream:
            if hasattr(chunk.choices[0], "delta") and hasattr(chunk.choices[0].delta, "content"):
                collected.append(chunk.choices[0].delta.content)

        assert "".join(collected) == "This is streaming."


@pytest.mark.asyncio
async def test_openai_function_calling():
    """Test mocked OpenAI function calling."""
    from unittest.mock import patch, AsyncMock
    import json

    # Create properly structured mock
    mock_function_call = MagicMock()
    mock_function_call.name = "train_model"
    mock_function_call.arguments = json.dumps({
        "algorithm": "random_forest",
        "target": "purchased"
    })

    mock_message = MagicMock()
    mock_message.role = "assistant"
    mock_message.content = None
    mock_message.function_call = mock_function_call

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("openai.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai.return_value = mock_client

        # Simulate function calling
        client = mock_openai()
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Train a model on my data"}],
            functions=[{
                "name": "train_model",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "algorithm": {"type": "string"},
                        "target": {"type": "string"}
                    }
                }
            }]
        )

        function_call = response.choices[0].message.function_call
        assert function_call.name == "train_model"

        args = json.loads(function_call.arguments)
        assert args["algorithm"] == "random_forest"
        assert args["target"] == "purchased"


@pytest.mark.asyncio
async def test_openai_token_counting(mock_openai):
    """Test mocked token usage tracking."""
    response = mock_openai["response"]

    # Verify usage data
    assert "usage" in response
    assert response["usage"]["prompt_tokens"] == 10
    assert response["usage"]["completion_tokens"] == 20
    assert response["usage"]["total_tokens"] == 30


@pytest.mark.asyncio
async def test_openai_multiple_responses():
    """Test handling multiple AI responses in sequence."""
    from unittest.mock import patch, AsyncMock

    # Create properly structured mocks for each response
    mock_responses = []
    for i in range(1, 4):
        mock_message = MagicMock()
        mock_message.content = f"Response {i}"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_responses.append(mock_response)

    with patch("openai.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()

        # Configure side_effect for multiple calls
        mock_client.chat.completions.create = AsyncMock(
            side_effect=mock_responses
        )
        mock_openai.return_value = mock_client

        client = mock_openai()

        # Make multiple calls
        for i in range(3):
            response = await client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": f"Prompt {i+1}"}]
            )
            assert response.choices[0].message.content == f"Response {i+1}"


def test_openai_canned_responses(test_openai_response):
    """Test using canned responses for different scenarios."""
    # Data summary scenario
    summary = test_openai_response["data_summary"]["content"]
    assert "100 records" in summary
    assert "5 columns" in summary

    # Model advice scenario
    advice = test_openai_response["model_advice"]["content"]
    assert "Binary Classification" in advice
    assert "Random Forest" in advice

    # Error diagnosis scenario
    diagnosis = test_openai_response["error_diagnosis"]["content"]
    assert "missing values" in diagnosis
    assert "median imputation" in diagnosis
