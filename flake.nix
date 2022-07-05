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
          pkgs.python39Packages.gunicorn
          pythonBuild
          pkgs.redis
        ];
        api = mach-nix-wrapper.buildPythonApplication {
          pname = "api.py";
          version = "1.0.0";
          src = ./.;
          requirements = requirements;
        };
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
          ];
        };
        defaultPackage = (pkgs.runCommand "igniteapi"
          {
            passAsFile = [ "text" ];
            preferLocalBuild = true;
            allowSubstitutes = false;
          } ''
          target=$out/bin/igniteapi
          mkdir -p "$(dirname "$target")"
          echo "#!/usr/bin/env ${pkgs.bash}/bin/bash" >> "$target"
          # echo "source <(head -n-1 ${api}/bin/api.py)" >> "$target"
          gunicorn=${pkgs.python39Packages.gunicorn}/bin/gunicorn
          cp ${api}/bin/.api.py-wrapped $out/api.py
          echo "$gunicorn --bind :5000 api --chdir $out/" >> "$target"
          chmod +x "$target"
        '');
      });
}
