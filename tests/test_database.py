from orchestrator import database


def test_save_and_load_run_with_iterations(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "history.db")

    run_id = database.save_run(
        goal="Test goal",
        refined_goal="Refined test goal",
        mode="writing",
        model_main="main-model",
        model_fast="fast-model",
        final_score=90,
        passed=True,
        stop_reason="passed",
        scores=[80, 90],
        run_dir="runs/test",
        final_output="Final answer",
        iterations_data=[
            {
                "iteration": 1,
                "critique": "Needs improvement",
                "revised_draft": "Better draft",
                "verdict": {"total_score": 80, "pass": False},
                "score": 80,
            },
            {
                "iteration": 2,
                "critique": "Good now",
                "revised_draft": "Best draft",
                "verdict": {"total_score": 90, "pass": True},
                "score": 90,
            },
        ],
    )

    loaded = database.load_run_by_id(run_id)

    assert loaded is not None
    assert loaded["goal"] == "Test goal"
    assert loaded["refined_goal"] == "Refined test goal"
    assert loaded["mode"] == "writing"
    assert loaded["passed"] is True
    assert loaded["scores_list"] == [80, 90]
    assert loaded["final_output"] == "Final answer"
    assert len(loaded["iterations_detail"]) == 2
    assert loaded["iterations_detail"][0]["score"] == 80
    assert loaded["iterations_detail"][1]["verdict"]["pass"] is True


def test_load_recent_runs_and_stats(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "history.db")

    database.save_run(
        goal="Goal 1",
        refined_goal="Refined 1",
        mode="general",
        model_main="main",
        model_fast="fast",
        final_score=70,
        passed=True,
        stop_reason="passed",
        scores=[70],
        run_dir="runs/one",
        final_output="Output 1",
    )

    database.save_run(
        goal="Goal 2",
        refined_goal="Refined 2",
        mode="coding",
        model_main="main",
        model_fast="fast",
        final_score=40,
        passed=False,
        stop_reason="failed",
        scores=[40],
        run_dir="runs/two",
        final_output="Output 2",
    )

    recent = database.load_recent_runs(2)
    stats = database.get_db_stats()

    assert len(recent) == 2
    assert stats["total_runs"] == 2
    assert stats["passed_runs"] == 1
    assert stats["average_score"] == 55.0


def test_delete_run_removes_run_and_iterations(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "history.db")

    run_id = database.save_run(
        goal="Delete me",
        refined_goal="Delete me refined",
        mode="general",
        model_main="main",
        model_fast="fast",
        final_score=75,
        passed=True,
        stop_reason="passed",
        scores=[75],
        run_dir="runs/delete",
        final_output="Output",
        iterations_data=[
            {
                "iteration": 1,
                "critique": "critique",
                "revised_draft": "draft",
                "verdict": {"total_score": 75},
                "score": 75,
            }
        ],
    )

    assert database.load_run_by_id(run_id) is not None

    database.delete_run(run_id)

    assert database.load_run_by_id(run_id) is None
