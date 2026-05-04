from pydantic import BaseModel, Field


class TimeRange(BaseModel):
    start_sec: float = Field(ge=0)
    end_sec: float = Field(ge=0)

    @property
    def duration_sec(self) -> float:
        return max(0.0, self.end_sec - self.start_sec)
