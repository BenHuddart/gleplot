"""Integration tests for Figure API and GLE generation."""

import pytest

import gleplot as glp


class TestFigureAPI:
    """Test Figure class API."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        """Create test figure."""
        glp.close()
        yield
        glp.close()

    def test_figure_creation(self):
        """Test creating a figure."""
        fig = glp.figure()
        assert fig is not None
        assert fig.figsize == (8, 6)

    def test_figure_custom_size(self):
        """Test figure with custom size."""
        fig = glp.figure(figsize=(10, 8))
        assert fig.figsize == (10, 8)

    def test_add_subplot(self):
        """Test adding subplot."""
        fig = glp.figure()
        ax = fig.add_subplot(111)

        assert ax is not None
        assert len(fig.axes_list) == 1

    def test_gca_creates_axes(self):
        """Test gca() creates axes if needed."""
        fig = glp.figure()
        ax = fig.gca()

        assert ax is not None
        assert len(fig.axes_list) == 1

    def test_convenience_functions(self):
        """Test module-level convenience functions."""
        glp.plot([1, 2, 3], [1, 2, 3])
        glp.scatter([1, 2, 3], [1, 2, 3])
        glp.bar([1, 2, 3], [10, 20, 30])
        glp.text(2, 2, "A")

        fig = glp.gcf()
        ax = fig.gca()

        assert len(ax.lines) == 1
        assert len(ax.scatters) == 1
        assert len(ax.bars) == 1
        assert len(ax.texts) == 1

    def test_module_savefig_supports_folder_option(self, tmp_path):
        """Test top-level savefig forwards the folder option."""
        glp.plot([1, 2, 3], [1, 4, 9])
        result = glp.savefig(str(tmp_path / "api_plot.gle"), folder=True)

        export_dir = tmp_path / "api_plot.gleplot"
        assert result == export_dir / "api_plot.gle"
        assert result.exists()
        assert len(list(export_dir.glob("*.dat"))) >= 1


class TestGLEGeneration:
    """Test GLE script generation."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        """Create test figure with plot."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
        yield
        glp.close()

    def test_gle_preamble(self):
        """Test GLE includes required preamble."""
        self.ax.plot([1, 2, 3], [1, 2, 3])

        gle = self.fig._generate_gle()

        assert "begin graph" in gle
        assert "end graph" in gle
        assert "size" in gle

    def test_gle_with_labels(self):
        """Test GLE includes axis labels."""
        self.ax.plot([1, 2, 3], [1, 2, 3])
        self.ax.set_xlabel("X Label")
        self.ax.set_ylabel("Y Label")
        self.ax.set_title("Title")

        gle = self.fig._generate_gle()

        assert "xtitle" in gle
        assert "ytitle" in gle
        assert "title" in gle

    def test_gle_with_log_scale(self):
        """Test GLE includes log scale."""
        self.ax.plot([1, 2, 3], [1, 2, 3])
        self.ax.set_xscale("log")

        gle = self.fig._generate_gle()

        # Check that xaxis has log keyword (format: "xaxis min X max Y log")
        assert "xaxis" in gle
        assert "log" in gle
        # Verify log appears on an xaxis line
        for line in gle.split("\n"):
            if "xaxis" in line and "log" in line:
                break
        else:
            pytest.fail("xaxis with log scale not found in GLE output")
