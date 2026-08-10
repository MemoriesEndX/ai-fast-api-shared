from typing import Union
from app.schemas.application import ApplicationEnum


class PromptService:
    """Service abstraction for managing system prompts per application context."""

    DEFAULT_SYSTEM_PROMPT = (
        "You are a helpful, accurate, and concise AI assistant for enterprise applications. "
        "Answer user queries clearly and professionally."
    )

    OWL_SYSTEM_PROMPT = (
        "You are an intelligent AI Learning Assistant for OWL Learning Management System (LMS). "
        "Your role is to assist students and instructors with course materials, learning objectives, "
        "curriculum guidance, and educational topics. Respond concisely, encouragingly, and clearly."
    )

    HR_CORNER_SYSTEM_PROMPT = (
        "You are an intelligent AI HR Assistant for HR Corner internal corporate portal. "
        "Your role is to assist employees with human resources procedures, workplace policies, "
        "leave requests, employee services, and general HR inquiries in a professional and helpful tone."
    )

    def get_system_prompt(self, application: Union[ApplicationEnum, str]) -> str:
        """Resolve the appropriate system prompt based on the requesting application context."""
        app_str = application.value if isinstance(application, ApplicationEnum) else str(application).lower()

        if app_str == ApplicationEnum.OWL.value:
            return self.OWL_SYSTEM_PROMPT
        elif app_str == ApplicationEnum.HR_CORNER.value:
            return self.HR_CORNER_SYSTEM_PROMPT
        else:
            return self.DEFAULT_SYSTEM_PROMPT
