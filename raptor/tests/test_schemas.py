import os
import pytest
from pydantic import ValidationError

os.environ.setdefault("COOKIE_ENCRYPTION_KEY", "3u8V_z5Fp3Uo54b1f4g7Y3k5l1pD_s1t4a5g7r8a9v0=")

from main import Scene, PlanOutput

def test_scene_duration_must_be_3_5_or_7():
    with pytest.raises(ValidationError):
        # 4초는 유효하지 않으므로 에러가 발생해야 함
        Scene(scene_index=0, duration_seconds=4, prompt="A test visual prompt that is long enough", subtitle="자막")

def test_scene_duration_accepts_valid_values():
    for d in [3, 5, 7]:
        scene = Scene(scene_index=0, duration_seconds=d, prompt="A test visual prompt that is long enough", subtitle="자막")
        assert scene.duration_seconds == d

def test_plan_requires_minimum_3_scenes():
    with pytest.raises(ValidationError):
        PlanOutput(product_name="X", selected_pattern="A", scenes=[],
                   title="T", hashtags=[], total_duration=0)

def test_plan_total_duration_must_match_scene_sum():
    scenes = [Scene(scene_index=i, duration_seconds=5, prompt="A test visual prompt that is long enough", subtitle="s")
              for i in range(3)]
    with pytest.raises(ValidationError):
        PlanOutput(product_name="X", selected_pattern="A", scenes=scenes,
                   title="T", hashtags=[], total_duration=99)  # 실제 합계: 15

def test_subtitle_max_200_chars():
    with pytest.raises(ValidationError):
        Scene(scene_index=0, duration_seconds=5, prompt="A test visual prompt that is long enough", subtitle="x" * 201)

def test_plan_max_8_scenes():
    scenes = [Scene(scene_index=i, duration_seconds=5, prompt="A test visual prompt that is long enough", subtitle="s")
              for i in range(9)]
    with pytest.raises(ValidationError):
        PlanOutput(product_name="X", selected_pattern="A", scenes=scenes,
                   title="T", hashtags=[], total_duration=45)
