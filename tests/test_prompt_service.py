from app.schemas.application import ApplicationEnum
from app.services.prompt_service import PromptService


def test_prompt_service_owl():
    service = PromptService()
    prompt = service.get_system_prompt(ApplicationEnum.OWL)
    assert "OWL" in prompt
    assert "Learning Assistant" in prompt


def test_prompt_service_hr_corner():
    service = PromptService()
    prompt = service.get_system_prompt(ApplicationEnum.HR_CORNER)
    assert "HR Corner" in prompt
    assert "HR Assistant" in prompt


def test_prompt_service_default():
    service = PromptService()
    prompt = service.get_system_prompt("unknown_app")
    assert "helpful" in prompt
