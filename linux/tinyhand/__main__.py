import os
import sys


def run():
    # TinyHand draws through X11: natively on X11 sessions and via XWayland on
    # Wayland, where a regular Wayland client can't make a full-screen overlay
    # that hides the cursor on every desktop.
    os.environ["GDK_BACKEND"] = os.environ.get("TINYHAND_GDK_BACKEND", "x11")
    if "--render-test" in sys.argv:
        from .tests import render_test

        return render_test(sys.argv[sys.argv.index("--render-test") + 1:])
    from .app import main

    return main()


if __name__ == "__main__":
    sys.exit(run())
