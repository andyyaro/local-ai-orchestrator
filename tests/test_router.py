from orchestrator.router import classify_path, get_path_config


# ── classify_path ────────────────────────────────────────────────────────────

def test_classify_path_fast_for_short_plain_goal():
    assert classify_path("Summarize the water cycle briefly.", "general") == "fast"


def test_classify_path_deep_for_complexity_keyword():
    goal = (
        "Write a comprehensive guide to Python decorators covering every "
        "detail of the metaprogramming model in careful depth."
    )
    assert classify_path(goal, "general") == "deep"


def test_classify_path_deep_for_coding_mode():
    assert classify_path("Write a helper function.", "coding") == "deep"


def test_classify_path_deep_for_debugging_mode():
    assert classify_path("Fix this bug.", "debugging") == "deep"


def test_classify_path_normal_for_goal_matching_neither_signal():
    goal = (
        "Write a clear explanation of how connection pooling works in a "
        "typical web application backend and why it matters for latency "
        "under load, covering the main tradeoffs teams usually run into."
    )
    assert len(goal.split()) > 25
    assert classify_path(goal, "general") == "normal"


def test_classify_path_override_wins_regardless_of_heuristic():
    long_goal = "Write a comprehensive, thorough, in-depth guide with tests."
    assert classify_path(long_goal, "coding", override="fast") == "fast"
    assert classify_path("hi", "general", override="deep") == "deep"


# ── get_path_config ──────────────────────────────────────────────────────────

def test_get_path_config_fast():
    config = get_path_config("fast")
    assert config["skip_planner"] is True
    assert config["skip_critic_fixer_loop"] is True
    assert config["max_loops"] == 1
    assert config["threshold"] == 60


def test_get_path_config_normal():
    config = get_path_config("normal")
    assert config["skip_planner"] is False
    assert config["skip_critic_fixer_loop"] is False
    assert config["max_loops"] == 2
    assert config["threshold"] == 70


def test_get_path_config_deep():
    config = get_path_config("deep")
    assert config["skip_planner"] is False
    assert config["skip_critic_fixer_loop"] is False
    assert config["max_loops"] == 4
    assert config["threshold"] == 80
