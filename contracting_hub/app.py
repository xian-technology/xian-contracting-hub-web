import reflex as rx


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.badge("Xian Ecosystem", color_scheme="green"),
            rx.heading("contracting-hub", size="8"),
            rx.text(
                "Curated smart contracts, version history, and deployment workflows.",
                size="4",
                color_scheme="gray",
            ),
            spacing="4",
            align="start",
        ),
        padding_y="5rem",
    )


app = rx.App()
app.add_page(index, route="/", title="contracting-hub")
