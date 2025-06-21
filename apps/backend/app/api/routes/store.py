from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from app.models.user_data import UserData
from app.auth.nextauth_auth import get_current_user_id
from pydantic import BaseModel

router = APIRouter()


class StoreDataRequest(BaseModel):
    fileName: str
    fileType: str
    headers: List[str]
    data: List[List[Any]]


@router.post("/")
async def store_data(
    data: StoreDataRequest, current_user_id: str = Depends(get_current_user_id)
):
    """
    Store the uploaded data in the database.
    """
    try:
        # Convert the data to the format expected by the UserData model
        formatted_data = []
        for row in data.data:
            row_dict = {}
            for i, value in enumerate(row):
                if i < len(data.headers):
                    row_dict[data.headers[i]] = value
            formatted_data.append(row_dict)

        # Create a new UserData document
        user_data = UserData(
            user_id=current_user_id,
            file_name=data.fileName,
            file_type=data.fileType,
            headers=data.headers,
            data=formatted_data,
        )

        # Save to database
        await user_data.insert()

        return {"message": "Data stored successfully", "id": str(user_data.id)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error storing data: {str(e)}")
