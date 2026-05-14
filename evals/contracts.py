"""Pydantic contracts matching Presenton pipeline (no FastAPI imports)."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class SlideOutlineModel(BaseModel):
    content: str


class PresentationOutlineModel(BaseModel):
    slides: List[SlideOutlineModel]

    def to_string(self) -> str:
        message = ""
        for i, slide in enumerate(self.slides):
            message += f"## Slide {i+1}:\n"
            message += f"  - Content: {slide} \n"
        return message


class PresentationStructureModel(BaseModel):
    slides: List[int] = Field(description="List of slide layout indexes")


class SlideLayoutModel(BaseModel):
    id: str
    name: str | None = None
    description: str | None = None
    json_schema: dict


class PresentationLayoutModel(BaseModel):
    name: str
    ordered: bool = Field(default=False)
    slides: List[SlideLayoutModel]

    def to_string(self) -> str:
        """Match `servers/fastapi/templates/presentation_layout.PresentationLayoutModel.to_string` (name + description per layout, no embedded JSON schemas)."""
        message = "## Presentation Layout\n\n"
        for index, slide in enumerate(self.slides):
            message += f"### Slide Layout: {index}\n"
            message += f"- Name: {slide.name or slide.json_schema.get('title')}\n"
            message += f"- Description: {slide.description}\n\n"
        return message


def get_presentation_outline_model_with_n_slides(n_slides: int):
    class SlideOutlineModelWithNSlides(SlideOutlineModel):
        content: str = Field(
            description="Markdown content for each slide",
            min_length=100,
            max_length=1200,
        )

    class PresentationOutlineModelWithNSlides(PresentationOutlineModel):
        slides: List[SlideOutlineModelWithNSlides] = Field(
            description="List of slide outlines",
            min_length=n_slides,
            max_length=n_slides,
        )

    return PresentationOutlineModelWithNSlides


def get_presentation_structure_model_with_n_slides(n_slides: int):
    class PresentationStructureModelWithNSlides(PresentationStructureModel):
        slides: List[int] = Field(
            description="List of slide layouts",
            min_length=n_slides,
            max_length=n_slides,
        )

    return PresentationStructureModelWithNSlides
