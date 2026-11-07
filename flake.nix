{
  description = "Dev environment for aria-garmin-sync";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python312
            uv
            google-cloud-sdk
            jq
          ];

          shellHook = ''
            export UV_PYTHON_DOWNLOADS=never
            if [ ! -d .venv ]; then
              uv venv --python ${pkgs.python312}/bin/python3
            fi
            source .venv/bin/activate
          '';
        };
      });
}
