class ParsedJob:
    def __init__(
        self,
        title=None,
        years_required=None,
        project_types=None
    ):
        self.title = title
        self.years_required = years_required
        self.project_types = project_types or []

    def __repr__(self):
        return (
            f"ParsedJob("
            f"title={self.title}, "
            f"years_required={self.years_required}, "
            f"project_types={self.project_types}"
            f")"
        )
