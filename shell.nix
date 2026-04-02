{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  packages = [
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.python311Packages.virtualenv
  ];

  shellHook = ''
    export QT_QPA_PLATFORM=${QT_QPA_PLATFORM:-xcb}
    echo "Image Blend Studio nix-shell ready."
    echo "Run: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && pip install -e ."
  '';
}
