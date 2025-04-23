import os
import json
import logging
import pandas as pd
from typing import Dict, Any, List, Optional
from openai import OpenAI
from app.models.user_data import UserData, AISummary

# Set up logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = None


def initialize_openai_client():
    global client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logging.error("OPENAI_API_KEY not set in environment variables")
        return
    client = OpenAI(api_key=api_key)
    logging.info("OpenAI client initialized successfully")


# Get the model name from environment variable, default to "gpt-4"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")
logger.info(f"Using OpenAI model: {OPENAI_MODEL}")


async def generate_dataset_summary(user_data_id: str) -> Optional[AISummary]:
    """
    Generate an AI summary of a dataset using OpenAI's GPT-4.

    Args:
        user_data_id: The ID of the UserData document

    Returns:
        An AISummary object if successful, None otherwise
    """
    try:
        # Get the UserData document
        user_data = await UserData.get(user_data_id)
        if not user_data:
            logger.error(f"UserData document with ID {user_data_id} not found")
            return None

        # Check if AI summary already exists
        if user_data.aiSummary:
            logger.info(
                f"AI summary already exists for dataset {user_data_id}, skipping generation"
            )
            return user_data.aiSummary

        # Prepare dataset summary for the prompt
        dataset_summary = prepare_dataset_summary(user_data)

        # Generate the AI summary
        ai_summary = await call_openai_api(dataset_summary)

        if ai_summary:
            # Update the UserData document with the AI summary
            user_data.aiSummary = ai_summary
            await user_data.save()
            logger.info(f"AI summary generated and saved for dataset {user_data_id}")
            return ai_summary
        else:
            logger.error(f"Failed to generate AI summary for dataset {user_data_id}")
            return None

    except Exception as e:
        logger.error(f"Error generating AI summary: {str(e)}")
        return None


def prepare_dataset_summary(user_data: UserData) -> Dict[str, Any]:
    """
    Prepare a summary of the dataset for the OpenAI prompt.

    Args:
        user_data: The UserData document

    Returns:
        A dictionary containing the dataset summary
    """
    # Extract basic information
    summary = {
        "filename": user_data.filename,
        "num_rows": user_data.num_rows,
        "num_columns": user_data.num_columns,
        "columns": [],
    }

    # Add column information
    for field in user_data.data_schema:
        column_info = {
            "name": field.field_name,
            "type": field.field_type,
            "data_type": field.data_type,
            "unique_values": field.unique_values,
            "missing_values": field.missing_values,
            "is_constant": field.is_constant,
            "is_high_cardinality": field.is_high_cardinality,
            "example_values": field.example_values[:5],  # Limit to 5 examples
        }
        summary["columns"].append(column_info)

    return summary


async def call_openai_api(dataset_summary: Dict[str, Any]) -> Optional[AISummary]:
    """
    Call the OpenAI API to generate an AI summary of the dataset.

    Args:
        dataset_summary: A dictionary containing the dataset summary

    Returns:
        An AISummary object if successful, None otherwise
    """
    if not client:
        logging.error("OpenAI client not initialized")
        return None

    try:
        # Convert the dataset summary to a JSON string
        dataset_json = json.dumps(dataset_summary, indent=2)

        # Create the system prompt
        system_prompt = """
        You are a data analyst AI assistant. Your task is to analyze the provided dataset and generate a comprehensive summary.
        Focus on identifying patterns, potential issues, relationships between variables, and providing actionable suggestions.
        
        Your response should be in the following JSON format:
        {
            "overview": "A concise overview of the dataset",
            "issues": ["List of potential issues or concerns with the data"],
            "relationships": ["List of identified relationships between variables"],
            "suggestions": ["List of suggestions for data analysis or improvements"],
            "rawMarkdown": "A detailed markdown analysis of the dataset"
        }
        
        Be thorough but concise. The rawMarkdown field should contain a complete analysis in markdown format.
        """

        # Create the user prompt
        user_prompt = f"""
        Please analyze the following dataset and provide a comprehensive summary:
        
        {dataset_json}
        
        Focus on:
        1. Identifying the main characteristics of the dataset
        2. Highlighting any data quality issues or anomalies
        3. Suggesting potential relationships between variables
        4. Providing recommendations for further analysis
        """

        # Call the OpenAI API
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )

        # Extract the response content
        content = response.choices[0].message.content

        # Parse the JSON response
        try:
            summary_json = json.loads(content)

            # Create and return an AISummary object
            return AISummary(
                overview=summary_json.get("overview", ""),
                issues=summary_json.get("issues", []),
                relationships=summary_json.get("relationships", []),
                suggestions=summary_json.get("suggestions", []),
                rawMarkdown=summary_json.get("rawMarkdown", ""),
            )
        except json.JSONDecodeError:
            logger.error("Failed to parse OpenAI response as JSON")
            return None

    except Exception as e:
        logger.error(f"Error calling OpenAI API: {str(e)}")
        return None
