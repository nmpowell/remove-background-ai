import click


@click.command()
@click.version_option(
    package_name="remove-background-ai", prog_name="remove-background-ai"
)
def cli() -> None:
    """Remove image backgrounds with OpenAI's GPT Image 2.5."""
