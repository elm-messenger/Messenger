#!/usr/bin/env python3

import typer
import os
import shutil
import json
import subprocess
from pathlib import Path
from .updater import Updater

app = typer.Typer(add_completion=False, help="Messenger CLI")
API_VERSION = "1.2.1"
CLI_VERSION = "0.6.0"

SCENE_DIR = "src/Scenes"
SCENEPROTO_DIR = "src/SceneProtos"
GC_DIR = "src/GlobalComponents"
ASSETS_DIR = "assets"
TEMP_REPO = "https://github.com/elm-messenger/messenger-templates.git"


def compress_json_file(path: str):
    path = Path(path)
    if not path.is_file():
        print(f"File not found: {path}")
        return
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    compressed = json.dumps(data, separators=(",", ":"))
    with path.open("w", encoding="utf-8") as f:
        f.write(compressed)


def execute_cmd(cmd: str, allow_err=False):
    result = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,  # decode bytes to string
    )
    if result.returncode != 0 and not allow_err:
        print(cmd, "command failed with exit code", result.returncode)
        print(result.stdout.strip())
        print(result.stderr.strip())
        exit(1)
    return result.returncode, result.stdout


class Messenger:
    config = None

    def __init__(self) -> None:
        """
        Check if `messenger.json` exists and load it.
        """
        if os.path.exists("messenger.json"):
            with open("messenger.json", "r") as f:
                self.config = json.load(f)
            if "version" not in self.config:
                raise Exception("Messenger API version not found in the config file.")
            if self.config["version"] != API_VERSION:
                raise Exception(
                    f"Messenger configuration file API version not matched. I'm using v{API_VERSION}. You can edit messenger.json manually to upgrade/downgrade."
                )
            # Add backwards compatibility for use_cdn and use_min fields
            if "use_cdn" not in self.config:
                self.config["use_cdn"] = False
            if "use_min" not in self.config:
                self.config["use_min"] = False
        else:
            raise Exception(
                "messenger.json not found. Are you in the project initialized by the Messenger? Try `messenger init <your-project-name>`."
            )
        if not os.path.exists(".messenger"):
            print("Messenger files not found. Initializing...")
            repo = self.config["template_repo"]
            if repo["tag"] == "":
                execute_cmd(f"git clone {repo["url"]} .messenger --depth=1")
            else:
                execute_cmd(
                    f"git clone -b {repo["tag"]} {repo["url"]} .messenger --depth=1"
                )

    def check_git_clean(self):
        res = execute_cmd("git status --porcelain")
        if res[1] != "":
            print(f"Your git repository is not clean. Please commit or stash your changes before using this command.")
            raise Exception(f"{res[1]}")

    def dump_config(self):
        with open("messenger.json", "w") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)
        if self.config["auto_commit"]:
            execute_cmd("git add .")


    def add_level(self, name: str, sceneproto: str):
        """
        Add a level
        """
        if not os.path.exists(SCENE_DIR):
            os.mkdir(SCENE_DIR)
        if sceneproto not in self.config["sceneprotos"]:
            raise Exception("Sceneproto doesn't exist.")
        if name in self.config["scenes"]:
            raise Exception("Level or scene already exists.")
        self.config["scenes"][name] = {
            "sceneproto": sceneproto,
            "raw": self.config["sceneprotos"][sceneproto]["raw"],
        }
        self.dump_config()
        os.mkdir(f"{SCENE_DIR}/{name}")
        self.config["sceneprotos"][sceneproto]["levels"].append(name)
        self.dump_config()
        raw = self.config["sceneprotos"][sceneproto]["raw"]
        if raw:
            Updater(
                [".messenger/sceneproto/Raw/Level.elm"],
                [f"{SCENE_DIR}/{name}/Model.elm"],
            ).rep(name).rep(sceneproto)
        else:
            Updater(
                [".messenger/sceneproto/Layered/Level.elm"],
                [f"{SCENE_DIR}/{name}/Model.elm"],
            ).rep(name).rep(sceneproto)

    def add_scene(self, scene: str, raw: bool, is_proto: bool, init: bool):
        """
        Add a scene
        """
        if is_proto:
            if not os.path.exists(SCENEPROTO_DIR):
                os.mkdir(SCENEPROTO_DIR)
            if scene in self.config["sceneprotos"]:
                raise Exception("Sceneproto already exists.")
            self.config["sceneprotos"][scene] = {
                "raw": raw,
                "levels": [],
            }
            self.dump_config()
            os.mkdir(f"{SCENEPROTO_DIR}/{scene}")

            Updater(
                [".messenger/scene/Init.elm"],
                [f"{SCENEPROTO_DIR}/{scene}/Init.elm"],
            ).rep("SceneProtos").rep(scene)
            if raw:
                Updater(
                    [".messenger/sceneproto/Raw/Model.elm"],
                    [f"{SCENEPROTO_DIR}/{scene}/Model.elm"],
                ).rep(scene)
            else:
                Updater(
                    [
                        ".messenger/sceneproto/Layered/Model.elm",
                        ".messenger/sceneproto/SceneBase.elm",
                    ],
                    [
                        f"{SCENEPROTO_DIR}/{scene}/Model.elm",
                        f"{SCENEPROTO_DIR}/{scene}/SceneBase.elm",
                    ],
                ).rep(scene)
        else:
            if not os.path.exists(SCENE_DIR):
                os.mkdir(SCENE_DIR)
            if scene in self.config["scenes"]:
                raise Exception("Scene already exists.")
            self.config["scenes"][scene] = {
                "raw": raw,
            }
            self.dump_config()
            os.mkdir(f"{SCENE_DIR}/{scene}")
            if init:
                Updater(
                    [".messenger/scene/Init.elm"],
                    [f"{SCENE_DIR}/{scene}/Init.elm"],
                ).rep("Scenes").rep(scene)
            if raw:
                Updater(
                    [".messenger/scene/Raw/Model.elm"],
                    [f"{SCENE_DIR}/{scene}/Model.elm"],
                ).rep(scene)
            else:
                Updater(
                    [
                        ".messenger/scene/Layered/Model.elm",
                        ".messenger/scene/SceneBase.elm",
                    ],
                    [
                        f"{SCENE_DIR}/{scene}/Model.elm",
                        f"{SCENE_DIR}/{scene}/SceneBase.elm",
                    ],
                ).rep(scene)


        if self.config["auto_commit"]:
            execute_cmd(f"git add .")

    def update_scenes(self):
        """
        Update scene settings (AllScenes and SceneSettings)
        """
        if not os.path.exists(SCENE_DIR):
            return
        scenes = sorted(self.config["scenes"])
        Updater([".messenger/scene/AllScenes.elm"], [f"{SCENE_DIR}/AllScenes.elm"]).rep(
            "\n".join([f"import Scenes.{l}.Model as {l}" for l in scenes])
        ).rep("\n        , ".join([f'( "{l}", {l}.scene )' for l in scenes]))
        if self.config["auto_commit"]:
            execute_cmd(f"git add .")

    def add_gc(self, name: str):
        if not os.path.exists(GC_DIR):
            os.mkdir(GC_DIR)
        os.makedirs(f"{GC_DIR}/{name}", exist_ok=True)
        if not os.path.exists(f"{GC_DIR}/{name}/Model.elm"):
            Updater(
                [".messenger/component/GlobalComponent/Model.elm"],
                [f"{GC_DIR}/{name}/Model.elm"],
            ).rep(name)
            if self.config["auto_commit"]:
                execute_cmd(f"git add .")
        else:
            raise Exception("Global component already exists.")

    def add_component(
        self, name: str, scene: str, dir: str, is_proto: bool, init: bool
    ):
        """
        Add a component
        """
        if is_proto:
            if scene not in self.config["sceneprotos"]:
                raise Exception("Sceneproto doesn't exist.")

            if os.path.exists(f"{SCENEPROTO_DIR}/{scene}/{dir}/{name}"):
                raise Exception("Component already exists.")

            if not os.path.exists(f"{SCENEPROTO_DIR}/{scene}/{dir}"):
                os.mkdir(f"{SCENEPROTO_DIR}/{scene}/{dir}")

            if not os.path.exists(f"{SCENEPROTO_DIR}/{scene}/SceneBase.elm"):
                Updater(
                    [".messenger/sceneproto/SceneBase.elm"],
                    [f"{SCENEPROTO_DIR}/{scene}/SceneBase.elm"],
                ).rep(scene)

            if not os.path.exists(f"{SCENEPROTO_DIR}/{scene}/{dir}/ComponentBase.elm"):
                Updater(
                    [".messenger/component/ComponentBase.elm"],
                    [f"{SCENEPROTO_DIR}/{scene}/{dir}/ComponentBase.elm"],
                ).rep("SceneProtos").rep(scene).rep(dir)

            self.dump_config()
            os.makedirs(f"{SCENEPROTO_DIR}/{scene}/{dir}/{name}", exist_ok=True)
            Updater(
                [
                    ".messenger/component/UserComponent/Model.elm",
                ],
                [
                    f"{SCENEPROTO_DIR}/{scene}/{dir}/{name}/Model.elm",
                ],
            ).rep("SceneProtos").rep(scene).rep(dir).rep(name)

            if init:
                Updater(
                    [".messenger/component/Init.elm"],
                    [f"{SCENEPROTO_DIR}/{scene}/{dir}/{name}/Init.elm"],
                ).rep("SceneProtos").rep(scene).rep(dir).rep(name)
        else:
            if scene not in self.config["scenes"]:
                raise Exception("Scene doesn't exist.")

            if os.path.exists(f"{SCENE_DIR}/{scene}/{dir}/{name}"):
                raise Exception("Component already exists.")

            if not os.path.exists(f"{SCENE_DIR}/{scene}/{dir}"):
                os.mkdir(f"{SCENE_DIR}/{scene}/{dir}")

            if not os.path.exists(f"{SCENE_DIR}/{scene}/{dir}/ComponentBase.elm"):
                Updater(
                    [".messenger/component/ComponentBase.elm"],
                    [f"{SCENE_DIR}/{scene}/{dir}/ComponentBase.elm"],
                ).rep("Scenes").rep(scene).rep(dir)

            if not os.path.exists(f"{SCENE_DIR}/{scene}/SceneBase.elm"):
                Updater(
                    [".messenger/scene/SceneBase.elm"],
                    [f"{SCENE_DIR}/{scene}/SceneBase.elm"],
                ).rep(scene)

            self.dump_config()
            os.makedirs(f"{SCENE_DIR}/{scene}/{dir}/{name}", exist_ok=True)
            Updater(
                [
                    ".messenger/component/UserComponent/Model.elm",
                ],
                [
                    f"{SCENE_DIR}/{scene}/{dir}/{name}/Model.elm",
                ],
            ).rep("Scenes").rep(scene).rep(dir).rep(name)

            if init:
                Updater(
                    [".messenger/component/Init.elm"],
                    [f"{SCENE_DIR}/{scene}/{dir}/{name}/Init.elm"],
                ).rep("Scenes").rep(scene).rep(dir).rep(name)

        if self.config["auto_commit"]:
            execute_cmd(f"git add .")

    def format(self):
        execute_cmd("elm-format src/ --yes")

    def add_layer(
        self,
        scene: str,
        layer: str,
        has_component: bool,
        is_proto: bool,
        dir: str,
        init: bool,
    ):
        """
        Add a layer to a scene
        """
        if is_proto:
            if scene not in self.config["sceneprotos"]:
                raise Exception("Scene doesn't exist.")
            if os.path.exists(f"{SCENEPROTO_DIR}/{scene}/{layer}"):
                raise Exception("Layer already exists.")
            if has_component and not os.path.exists(
                f"{SCENEPROTO_DIR}/{scene}/{dir}/ComponentBase.elm"
            ):
                os.makedirs(f"{SCENEPROTO_DIR}/{scene}/{dir}", exist_ok=True)
                Updater(
                    [".messenger/component/ComponentBase.elm"],
                    [f"{SCENEPROTO_DIR}/{scene}/{dir}/ComponentBase.elm"],
                ).rep("SceneProtos").rep(scene).rep(dir)

            if not os.path.exists(f"{SCENEPROTO_DIR}/{scene}/SceneBase.elm"):
                Updater(
                    [".messenger/sceneproto/SceneBase.elm"],
                    [f"{SCENEPROTO_DIR}/{scene}/SceneBase.elm"],
                ).rep(scene)
            self.dump_config()
            os.mkdir(f"{SCENEPROTO_DIR}/{scene}/{layer}")
            if init:
                Updater(
                    [".messenger/layer/Init.elm"],
                    [f"{SCENEPROTO_DIR}/{scene}/{layer}/Init.elm"],
                ).rep("SceneProtos").rep(scene).rep(layer)
            if has_component:
                Updater(
                    [
                        ".messenger/layer/ModelC.elm",
                    ],
                    [
                        f"{SCENEPROTO_DIR}/{scene}/{layer}/Model.elm",
                    ],
                ).rep("SceneProtos").rep(scene).rep(layer).rep(dir)
            else:
                Updater(
                    [
                        ".messenger/layer/Model.elm",
                    ],
                    [
                        f"{SCENEPROTO_DIR}/{scene}/{layer}/Model.elm",
                    ],
                ).rep("SceneProtos").rep(scene).rep(layer)
        else:
            if scene not in self.config["scenes"]:
                raise Exception("Scene doesn't exist.")
            if os.path.exists(f"{SCENE_DIR}/{scene}/{layer}"):
                raise Exception("Layer already exists.")
            if has_component and not os.path.exists(
                f"{SCENE_DIR}/{scene}/{dir}/ComponentBase.elm"
            ):
                os.makedirs(f"{SCENE_DIR}/{scene}/{dir}", exist_ok=True)
                Updater(
                    [".messenger/component/ComponentBase.elm"],
                    [f"{SCENE_DIR}/{scene}/{dir}/ComponentBase.elm"],
                ).rep("Scenes").rep(scene).rep(dir)

            if not os.path.exists(f"{SCENE_DIR}/{scene}/SceneBase.elm"):
                Updater(
                    [".messenger/scene/SceneBase.elm"],
                    [f"{SCENE_DIR}/{scene}/SceneBase.elm"],
                ).rep(scene)
            self.dump_config()
            os.mkdir(f"{SCENE_DIR}/{scene}/{layer}")
            if init:
                Updater(
                    [".messenger/layer/Init.elm"],
                    [f"{SCENE_DIR}/{scene}/{layer}/Init.elm"],
                ).rep("Scenes").rep(scene).rep(layer)
            if has_component:
                Updater(
                    [
                        ".messenger/layer/ModelC.elm",
                    ],
                    [
                        f"{SCENE_DIR}/{scene}/{layer}/Model.elm",
                    ],
                ).rep("Scenes").rep(scene).rep(layer).rep(dir)
            else:
                Updater(
                    [
                        ".messenger/layer/Model.elm",
                    ],
                    [
                        f"{SCENE_DIR}/{scene}/{layer}/Model.elm",
                    ],
                ).rep("Scenes").rep(scene).rep(layer)

        if self.config["auto_commit"]:
            execute_cmd(f"git add .")

    def install_font(self, filepath, name, font_size, range, charset_file, reuse, curpng):
        """
        Install a custom font
        """
        output_texture = f"{ASSETS_DIR}/fonts/font_{curpng}.png"
        output_cfg = f"{ASSETS_DIR}/fonts/font_{curpng}.cfg"
        ext = Path(filepath).suffix
        new_name = f"{name}{ext}"
        shutil.copy(filepath, f"{ASSETS_DIR}/fonts/{new_name}")
        charset_cmd = f"-i {charset_file}" if charset_file else ""
        reuse_cmd = f"--reuse {output_cfg}" if reuse else ""
        cmd = f"msdf-bmfont --smart-size --pot -d 2 -s {font_size} -r {range} {charset_cmd} -f json {reuse_cmd} -o {output_texture} {ASSETS_DIR}/fonts/{new_name}"
        # print(cmd)
        execute_cmd(cmd)
        os.remove(f"{ASSETS_DIR}/fonts/{new_name}")
        compress_json_file(f"{ASSETS_DIR}/fonts/{name}.json")
        print(
            f'Success. Now add `("{name}", FontRes "{output_texture}" "assets/fonts/{name}.json")` to `allFont` in `src/Lib/Resources.elm`.'
        )


def check_name(name: str):
    """
    Check if the the first character of the name is Capital
    """
    if name[0].islower():
        return name[0].capitalize() + name[1:]
    else:
        return name
    

def get_latest_version(package):
    import urllib.request
    import re

    url = f"https://package.elm-lang.org/packages/{package}/latest"
    package = package.split("/")[-1]
    with urllib.request.urlopen(url) as response:
        html = response.read().decode('utf-8')
    match = re.search(fr"<title>{re.escape(package)} ([^<]+)</title>", html)
    if match:
        return match.group(1)
    else:
        return "Unknown"


def get_current_commit(repo_path):
    """Get current commit hash of a git repository"""
    try:
        code, output = execute_cmd(f"git -C {repo_path} rev-parse HEAD", allow_err=True)
        if code == 0:
            return output.strip()
        return None
    except:
        return None


def get_remote_commit(repo_url, branch_or_tag=""):
    """Get latest commit hash from remote repository"""
    try:
        if branch_or_tag:
            code, output = execute_cmd(f"git ls-remote {repo_url} {branch_or_tag}", allow_err=True)
        else:
            code, output = execute_cmd(f"git ls-remote {repo_url} HEAD", allow_err=True)
        
        if code == 0 and output.strip():
            return output.strip().split()[0]
        return None
    except:
        return None


def compare_public_files(use_cdn, use_min):
    """Compare necessary public files between local and template"""
    import filecmp
    
    differences = []
    
    rmt_html = "index.local.html"
    if use_cdn:
        if use_min:
            rmt_html = "index.min.html"
        else:
            rmt_html = "index.html"

    # Define files to compare based on configuration
    files_to_check = [
        ("index.html", rmt_html),
        ("elm-audio.js", "elm-audio.js"),
        ("elm-messenger.js", "elm-messenger.js")
    ]
    
    # Add regl.js only if using local regl
    if not use_cdn:
        files_to_check.append(("regl.js", "regl.min.js" if use_min else "regl.js"))
    
    for local_file, template_file in files_to_check:
        local_path = os.path.join("public", local_file)
        template_path = os.path.join(".messenger/public", template_file)
        
        if not os.path.exists(local_path):
            differences.append(f"Missing local file: {local_file}")
        elif not os.path.exists(template_path):
            differences.append(f"Missing template file: {template_file}")
        elif not filecmp.cmp(local_path, template_path, shallow=False):
            differences.append(f"Different: {local_file}")
    
    return differences


def check_dependencies(has_index, has_elm):
    warns = []
    outdated = False
    if not has_index:
        raise Exception("No html file found in public/. Try `messenger sync` to initialize.")
    if not has_elm:
        raise Exception("No elm.json found. Try `messenger sync` to initialize.")
    # check elm.json
    packages = ["linsyking/messenger-core", "linsyking/elm-regl", "linsyking/messenger-extra"]
    with open("elm.json", "r") as f:
        data = json.load(f)
    deps = data["dependencies"]["direct"]
    deps.update(data["dependencies"]["indirect"])
    print(f"{'Elm Package':<35} {'Current':<10} {'Latest'}")
    print("-" * 60)
    for name in packages:
        if name in deps:
            current = deps[name]
        elif name == "linsyking/messenger-extra":
            continue
        else:
            warns.append(f"Warning: {name[len('linsyking/'):]} is not in elm.json dependencies.")
            current = "X"
            outdated = True
        latest = get_latest_version(name)
        print(f"{name:<35} {current:<10} {latest}")
        # Check if current version is different from latest
        if current != "X" and current != latest:
            outdated = True
    if warns:
        print("\n" + "\n".join(warns))
    return outdated
    

@app.command()
def init(
    name: str,
    template_repo=typer.Option(
        f"{TEMP_REPO}",
        "--template-repo",
        "-t",
        help="Use customized repository for cloning templates.",
    ),
    template_tag=typer.Option(
        None,
        "--template-tag",
        "-b",
        help="Use the tag or branch of the repository to clone.",
    ),
    auto_commit: bool = typer.Option(
        False, "--auto-commit", "-g", help="Automatically commit template codes."
    ),
    use_cdn: bool = typer.Option(
        False,
        "--use-cdn",
        help="Use jsdelivr CDN for elm-regl JS file.",
    ),
    minimal: bool = typer.Option(
        False,
        "--min",
        help="Use minimal regl JS that has no builtin font.",
    ),
    current_dir: bool = typer.Option(
        False, "--current-dir", "-c", help="Create the project in the current directory."
    ),
):
    execute_cmd("elm")
    execute_cmd("elm-format")
    cur_hint = f"Create a directory named {name}" if not current_dir else f"Use the current directory, project name {name} will be ignored"
    commit_hint = "\n- Initialize a git repository and commit the template codes" if auto_commit else ""
    input(
        f"""Thanks for using Messenger.
See https://github.com/linsyking/Messenger for more information.
Here is my plan:

- {cur_hint}
- Install the core Messenger library
- Install the elm packages needed {commit_hint}

Press Enter to continue
"""
    )
    if not current_dir:
        os.makedirs(name, exist_ok=True)
        os.chdir(name)
    print("Cloning templates...")
    if template_tag:
        execute_cmd(f"git clone -b {template_tag} {template_repo} .messenger --depth=1")
    else:
        template_tag = ""
        execute_cmd(f"git clone {template_repo} .messenger --depth=1")
    if os.path.exists("./src"):
        raise FileExistsError("src directory already exists. Please remove or rename it first.")
    shutil.copytree(".messenger/src/", "./src")
    os.makedirs("public", exist_ok=True)
    shutil.copy(".messenger/public/elm-audio.js", "./public/elm-audio.js")
    shutil.copy(".messenger/public/elm-messenger.js", "./public/elm-messenger.js")
    shutil.copy(".messenger/public/style.css", "./public/style.css")
    if use_cdn:
        if minimal:
            shutil.copy(".messenger/public/index.min.html", "./public/index.html")
        else:
            shutil.copy(".messenger/public/index.html", "./public/index.html")
    else:
        shutil.copy(".messenger/public/index.local.html", "./public/index.html")
        if minimal:
            shutil.copy(".messenger/public/regl.min.js", "./public/regl.js")
        else:
            shutil.copy(".messenger/public/regl.js", "./public/regl.js")
    shutil.copy(".messenger/.gitignore", "./.gitignore")
    shutil.copy(".messenger/Makefile", "./Makefile")
    shutil.copy(".messenger/elm.json", "./elm.json")

    os.makedirs(SCENE_DIR, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)
    os.makedirs(f"{ASSETS_DIR}/fonts", exist_ok=True)

    print("Creating messenger.json...")
    initObject = {
        "version": API_VERSION,
        "template_repo": {
            "url": template_repo,
            "tag": template_tag,
        },
        "auto_commit": auto_commit,
        "use_cdn": use_cdn,
        "use_min": minimal,
        "scenes": {},
        "sceneprotos": {},
    }
    with open("messenger.json", "w") as f:
        json.dump(initObject, f, indent=4, ensure_ascii=False)
    print("Installing dependencies...")
    execute_cmd("elm make", allow_err=True)

    if auto_commit: 
        if not execute_cmd("git rev-parse --is-inside-work-tree", allow_err=True) == 0:
            print("Initializing git repository...")
            execute_cmd("git init")
        execute_cmd(f"git add .")
        execute_cmd("git commit -m 'build(Messenger): initialize project'")
    print("Done!")
    hint = f" go to {name} and" if not current_dir else ""
    print(f"Now please{hint} add scenes and components.")


@app.command()
def component(
    scene: str,
    name: str,
    compdir: str = typer.Option(
        "Components", "--cdir", "-cd", help="Directory to store components."
    ),
    is_proto: bool = typer.Option(
        False, "--proto", "-p", help="Create a component in sceneproto."
    ),
    init: bool = typer.Option(False, "--init", "-i", help="Create a `Init.elm` file."),
):
    name = check_name(name)
    scene = check_name(scene)
    compdir = check_name(compdir)
    msg = Messenger()
    input(
        f"You are going to create a component named {name} in {'SceneProtos' if is_proto else 'Scenes'}/{scene}/{compdir}, continue?"
    )
    if msg.config["auto_commit"]:
        msg.check_git_clean()
    msg.add_component(name, scene, compdir, is_proto, init)
    msg.format()
    if msg.config["auto_commit"]:
        execute_cmd(
            f"git commit -m 'build(Messenger): initialize component {name} {f"in {compdir}" if compdir != "Components" else ""} in {"sceneProto" if is_proto else "scene"} {scene}'"
        )
    print("Done!")


@app.command()
def gc(name: str):
    name = check_name(name)
    msg = Messenger()
    input(f"You are going to create a global component named {name}, continue?")
    if msg.config["auto_commit"]:
        msg.check_git_clean()
    msg.add_gc(name)
    msg.format()
    if msg.config["auto_commit"]:
        execute_cmd(f"git commit -m 'build(Messenger): initialize global component {name}'")
    print("Done!")


@app.command()
def scene(
    name: str,
    raw: bool = typer.Option(False, "--raw", help="Use raw scene without layers."),
    is_proto: bool = typer.Option(False, "--proto", "-p", help="Create a sceneproto."),
    init: bool = typer.Option(False, "--init", "-i", help="Create a `Init.elm` file."),
):
    name = check_name(name)
    msg = Messenger()
    input(
        f"You are going to create a {'raw ' if raw else ''}{'sceneproto' if is_proto else 'scene'} named {name}, continue?"
    )
    if msg.config["auto_commit"]:
        msg.check_git_clean()
    msg.add_scene(name, raw, is_proto, init)
    msg.update_scenes()
    msg.format()
    if msg.config["auto_commit"]:
        execute_cmd(f"git commit -m 'build(Messenger): initialize {"sceneproto" if is_proto else "scene"} {name}'")
    print("Done!")


@app.command()
def level(sceneproto: str, name: str):
    name = check_name(name)
    sceneproto = check_name(sceneproto)
    msg = Messenger()
    input(
        f"You are going to create a level named {name} from sceneproto {sceneproto}, continue?"
    )
    if msg.config["auto_commit"]:
        msg.check_git_clean()
    msg.add_level(name, sceneproto)
    msg.update_scenes()
    msg.format()
    if msg.config["auto_commit"]:
        execute_cmd(
            f"git commit -m 'build(Messenger): initialize level {name} from sceneproto {sceneproto}'"
        )
    print("Done!")


@app.command()
def layer(
    scene: str,
    layer: str,
    has_component: bool = typer.Option(
        False, "--with-component", "-c", help="Use components in this layer."
    ),
    compdir: str = typer.Option(
        "Components", "--cdir", "-cd", help="Directory of components in the scene."
    ),
    is_proto: bool = typer.Option(
        False, "--proto", "-p", help="Create a layer in sceneproto."
    ),
    init: bool = typer.Option(False, "--init", "-i", help="Create a `Init.elm` file."),
):
    scene = check_name(scene)
    layer = check_name(layer)
    msg = Messenger()
    input(
        f"You are going to create a layer named {layer} under {'sceneproto' if is_proto else 'scene'} {scene}, continue?"
    )
    if msg.config["auto_commit"]:
        msg.check_git_clean()
    msg.add_layer(scene, layer, has_component, is_proto, compdir, init)
    msg.format()
    if msg.config["auto_commit"]:
        execute_cmd(
            f"git commit -m 'build(Messenger): initialize layer {layer} under {"sceneproto" if is_proto else "scene"} {scene}'"
        )
    print("Done!")



@app.command()
def remove(
    type: str,
    name: str,
    remove: bool = typer.Option(False, "--rm", help="Also remove the modules."),
    remove_levels: bool = typer.Option(
        False, "--rml", help="Remove all levels in the sceneproto."
    ),
):
    name = check_name(name)
    msg = Messenger()
    input(f"You are going to remove {name} ({type}), continue?")
    if type == "scene":
        if name not in msg.config["scenes"]:
            raise Exception("Scene doesn't exist.")
        if "sceneproto" in msg.config["scenes"][name]:
            sp = msg.config["scenes"][name]["sceneproto"]
            msg.config["sceneprotos"][sp]["levels"].remove(name)
        msg.config["scenes"].pop(name)
        msg.update_scenes()
        if remove:
            shutil.rmtree(f"{SCENE_DIR}/{name}")
    elif type == "sceneproto":
        if name not in msg.config["sceneprotos"]:
            raise Exception("Sceneproto doesn't exist.")
        if len(msg.config["sceneprotos"][name]["levels"]) > 0:
            if remove_levels:
                for level in msg.config["sceneprotos"][name]["levels"]:
                    msg.config["scenes"].pop(level)
                    if remove:
                        shutil.rmtree(f"{SCENE_DIR}/{level}")
            else:
                raise Exception(
                    "There are levels using the sceneproto. Please remove them first."
                )
        msg.config["sceneprotos"].pop(name)
        if remove:
            shutil.rmtree(f"{SCENEPROTO_DIR}/{name}")
    else:
        print("No such type.")
    msg.dump_config()


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def font(
    ctx : typer.Context,
    range : int =typer.Option(4, "--range", help="Set the distance range."),
):
    """
    Install custom fonts for use in your Messenger project.
    Usage: `messenger font FONT1 FONT2...` where each FONT is `<font_file> [-n <name>] [-i <charset_file>] [-s <font_size>]`.
    """
    args = ctx.args
    # Check if the tool exists
    execute_cmd("msdf-bmfont -h")
    i = 0
    results = []
    currentObj = None
    while i < len(args):
        obj = args[i]
        i += 1
        if currentObj == None:
            currentObj = {"file": obj, "name": None, "font_size": 40, "charset": None}
        else:
            if obj == "-n":
                currentObj["name"] = args[i]
                i += 1
            elif obj == "-i":
                currentObj["charset"] = args[i]
                i += 1
            elif obj == "-s":
                currentObj["font_size"] = int(args[i])
                i += 1
            else:
                results.append(currentObj)
                currentObj = None
                i -= 1
    if currentObj == None:
        print("No font files provided.")
        exit(0)
    results.append(currentObj)
    for f in results:
        if f["name"] is None:
            f["name"] = Path(f["file"]).stem
    for f in results:
        print(f['name'], "from", f['file'])
    input(f"You are going to install the above font(s), continue?")
    msg = Messenger()
    curpng = 0
    while 1:
        output_texture = f"{ASSETS_DIR}/fonts/font_{curpng}.png"
        if not os.path.exists(output_texture):
            break
        curpng += 1
    for f in results:
        msg.install_font(f['file'], f['name'], f['font_size'], range, f['charset'], True, curpng)
    os.remove(f"{ASSETS_DIR}/fonts/font_{curpng}.cfg")
    # Fix: use the last's font's texture settings
    lastFont = results[len(results) - 1]
    output_json = f"{ASSETS_DIR}/fonts/{lastFont["name"]}.json"
    with open(output_json, "r") as f:
        lastFontJson = json.load(f)
    scaleW = lastFontJson["common"]["scaleW"]
    scaleH = lastFontJson["common"]["scaleH"]
    for f in results:
        output_json = f"{ASSETS_DIR}/fonts/{f["name"]}.json"
        with open(output_json, "r") as f:
            currentJson = json.load(f)
        currentJson["common"]["scaleW"] = scaleW
        currentJson["common"]["scaleH"] = scaleH
        with open(output_json, "w") as f:
            json.dump(currentJson, f)


@app.command()
def sync(
    force: bool = typer.Option(
        False, "--force", "-f", help="Force sync, disable all checks and replace dependencies in public/ forcibly."
    ),
    repo: str = typer.Option(
        "", "--template-repo", "-t", help="The new repository to sync from, empty for no change."
    ),
    tag: str = typer.Option(
        "", "--template-tag", "-b", help="The new tag or branch to sync from, empty for no change."
    ),
    ll: bool = typer.Option(
        False, "--list", "-l", help="List the current dependencies version and latest version on remote."
    ),
):
    """
    Sync your project with the latest templates and dependencies from remote repositories. Updates Elm packages, JavaScript files (elm-audio.js, elm-messenger.js, regl.js), and elm.json to match the latest versions. Use --list to check current vs latest versions without making changes.
    """
    msg = Messenger()
    has_index = os.path.exists("public/index.html")
    has_elm = os.path.exists("elm.json")
    has_messenger_dir = os.path.exists(".messenger")
    
    # Read use_cdn and use_min from messenger.json
    use_cdn = msg.config.get("use_cdn", False)
    use_min = msg.config.get("use_min", False)
    repo_url = msg.config["template_repo"]["url"] if msg.config["template_repo"]["url"] else TEMP_REPO
    repo_tag = msg.config["template_repo"]["tag"] if msg.config["template_repo"]["tag"] else ""
    current_commit = get_current_commit(".messenger") if has_messenger_dir else ""
    remote_commit = get_remote_commit(repo_url, repo_tag)
    
    if ll:
        needs_update = False
        
        # Check elm dependencies and track if any are outdated
        if check_dependencies(has_index, has_elm):
            needs_update = True

        # Check template repository status
        if has_messenger_dir:
            print(f"\n{'Template Repository':<35} {'Current':<10} {'Latest'}")
            print("-" * 60)
            current_display = current_commit[:8] if current_commit else "Unknown"
            latest_display = remote_commit[:8] if remote_commit else "Unknown"
            print(f"{'Templates':<35} {current_display:<10} {latest_display}")
            
            # Check if template needs update
            if current_commit and remote_commit and current_commit != remote_commit:
                needs_update = True
        
        # Check local public/ vs .messenger/public/ differences
        if has_messenger_dir:
            print(f"\n{'Public Files Comparison'}")
            print("-" * 25)
            differences = compare_public_files(use_cdn, use_min)
            if differences:
                print("Differences found:")
                for diff in differences:
                    print(f"  {diff}")
                needs_update = True
            else:
                print("All public files match templates")
        
        exit(1 if needs_update else 0)

    input(
        """You are going to sync the templates from remote and update the dependencies.
Here is my plan:

- Remove the current templates and re-clone them if force is set or the templates are out of date
- Overwrite the js dependencies in the public/ directory with the latest templates
- Update elm.json with the latest templates

Note that other changes in the latest templates will not be applied.

Press Enter to continue
"""
    )
    if msg.config["auto_commit"]:
        msg.check_git_clean()
    
    # Check if sync is needed
    if not force and has_messenger_dir:
        if current_commit and remote_commit and current_commit == remote_commit:
            print("Templates are already up to date.")
            differences = compare_public_files(use_cdn, use_min)
            if not differences:
                print("Local public files match templates.")
                print("No sync needed. Use --force to sync anyway.")
                return
            else:
                print("However, local public files have differences:")
                for diff in differences:
                    print(f"  {diff}")
                answer = input("Do you want to sync anyway? (y/N): ")
                if answer.lower() != 'y':
                    return
    
    # check file changes
    if use_cdn:
        temp_js = ""
        if use_min:
            temp_html = "public/index.min.html"
        else:
            temp_html = "public/index.html"
    else:
        temp_html = "public/index.local.html"
        if use_min:
            temp_js = "public/regl.min.js"
        else:
            temp_js = "public/regl.js"
    # update .messenger
    if tag != "":
        msg.config["template_repo"]["tag"] = tag
    if repo != "":
        msg.config["template_repo"]["url"] = repo
    
    # Check if we need to re-clone templates
    need_reclone = force
    if not force and has_messenger_dir:
        if not current_commit or not remote_commit or current_commit != remote_commit:
            need_reclone = True
            print("Templates are out of date, updating...")
        else:
            print("Templates are already up to date, skipping re-clone...")
    else:
        need_reclone = True
    
    if need_reclone:
        print("Syncing templates from remote...")
        if has_messenger_dir and not force:
            os.chdir(".messenger")
            try: 
                msg.check_git_clean()
            except Exception as e:
                print(f"Templates directory not clean! \n{e}")
                print("DO NOT manually modify the local templates here, your work will be lost when syncing!")
                print("Maintain a separate repo on remote for your changes. Or manage dependencies manually.")
                raise Exception("Please commit or stash your changes and try to sync again.")
            os.chdir("..")
        
        if has_messenger_dir:
            shutil.rmtree(".messenger")
        
        if repo_tag != "":
            execute_cmd(f"git clone -b {repo_tag} {repo_url} .messenger --depth=1")
        else:
            execute_cmd(f"git clone {repo_url} .messenger --depth=1")
    
    msg.dump_config()
    # update public/
    print("Updating public/ directory...")
    if not has_index:
        shutil.copy(f".messenger/public/{temp_html}", "./public/index.html")
    shutil.copy(".messenger/public/elm-audio.js", "./public/elm-audio.js")
    shutil.copy(".messenger/public/elm-messenger.js", "./public/elm-messenger.js")
    if not use_cdn:
        shutil.copy(f".messenger/{temp_js}", "./public/regl.js")
    elif has_index and need_reclone:
        print(f"You are using jsdelivr CDN for elm-regl JS file, please check the latest version in .messenger/{temp_html}.")
    # update elm.json
    print("Updating elm dependencies...")
    if has_elm:
        with open("elm.json", "r") as f:
            origin_data = json.load(f)
        with open(".messenger/elm.json", "r") as f:
            temp_data = json.load(f)
        for name, version in temp_data["dependencies"]["direct"].items():
            origin_data["dependencies"]["direct"][name] = version
        for name, version in temp_data["dependencies"]["indirect"].items():
            origin_data["dependencies"]["indirect"][name] = version
        with open("elm.json", "w") as f:
            json.dump(origin_data, f, indent=4, ensure_ascii=False)
    else:
        shutil.copy(".messenger/elm.json", "./elm.json")
    if msg.config["auto_commit"]:
        execute_cmd("git add .")
        execute_cmd("git commit -m 'build(Messenger): sync templates and update dependencies from remote'")
    print("Done!")
    # print("Now please check the new changes in the templates and update your project if necessary.")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v", help="Show the version of Messenger CLI."
    ),
):
    """
    Messenger CLI - A command line tool for Messenger projects.
    """
    if ctx.invoked_subcommand is None and not version:
        typer.echo(ctx.get_help())
    if version:
        print(f"Messenger CLI v{CLI_VERSION}, configuration file scheme v{API_VERSION}")



if __name__ == "__main__":
    app()
