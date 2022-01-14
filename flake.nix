{
  description = "Flake to manage python workspace";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/master";
    flake-utils.url = "github:numtide/flake-utils";
    mach-nix.url = "github:DavHau/mach-nix?ref=3.3.0";
  };

  outputs = { self, nixpkgs, flake-utils, mach-nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        system = "x86_64-linux";
        python = "python39";
        pkgs = import nixpkgs {
          inherit system;
        };
        # https://github.com/DavHau/mach-nix/issues/153#issuecomment-717690154
        mach-nix-wrapper = import mach-nix { inherit pkgs python; };
        requirements = builtins.readFile ./requirements.txt;
        pythonBuild = mach-nix-wrapper.mkPython {
          inherit requirements;
        };
        # app requirements
        dependencies = [
          pythonBuild
        ];
      in
      {
        devShell = pkgs.mkShell {
          buildInputs = [
            # dev packages
            mach-nix
            (pkgs.${python}.withPackages
              (ps: with ps; [ pip pyflakes ]))
          ];
          packages = dependencies ++ [
            # Whatever else we may need to debug
            pkgs.redis
          ];
        };
        defaultPackage = mach-nix-wrapper.buildPythonApplication ./.;
      });
}
