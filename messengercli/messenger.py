#!/usr/bin/env python3

import re
import typer
import os
import shutil
import json
import subprocess
from pathlib import Path
from .updater import Updater

app = typer.Typer(add_completion=False, help="Messenger CLI")
API_VERSION = "1.2.0"

SCENE_DIR = "src/Scenes"
SCENEPROTO_DIR = "src/SceneProtos"
GC_DIR = "src/GlobalComponents"
ASSETS_DIR = "assets"


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

    def check_git_clean():
        res = execute_cmd("git status --porcelain")
        if res[1] != "":
            print("Your git repository is not clean. Please commit or stash your changes before using this command.")
            print(res[1])
            exit(1)

    def dump_config(self):
        with open("messenger.json", "w") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)
        if self.config["auto_commit"]:
            execute_cmd("git add ./messenger.json")

    def update_config(self):
        self.config["version"] = API_VERSION
        self.config["template_repo"] = {"url": "", "tag": ""}
        self.config["auto_commit"] = False
        if execute_cmd("git rev-parse --is-inside-work-tree", allow_err=True)[0] == 0 and self.config.get("auto_commit"):
            self.config["auto_commit"] = True
        self.config["scenes"] = {}
        self.config["sceneprotos"] = {}
                    
        os.chdir(".messenger")
        if execute_cmd("git rev-parse --is-inside-work-tree", allow_err=True)[0] != 0:
            print("No git repository found in .messenger directory.")
        else:
            urlcode, urlres = execute_cmd("git remote get-url origin", allow_err=True)
            if urlcode == 0:
                self.config["template_repo"]["url"] = urlres.strip()
            else:
                print("No remote repository found. Please set the remote repository URL in messenger.json manually.")
            tagcode, tagres = execute_cmd("git describe --tags --exact-match", allow_err=True)
            if tagcode == 0:
                self.config["template_repo"]["tag"] = tagres.strip()
            else:
                branchcode, branchres = execute_cmd("git rev-parse --abbrev-ref @{u}", allow_err=True)
                if branchcode == 0:
                    if re.fullmatch(r'origin/(main|master)', branchres.strip()):
                        self.config["template_repo"]["tag"] = "" 
                    else:
                        self.config["template_repo"]["tag"] = branchres.strip()[len('origin/'):]
                else:
                    print("No tag or branch found. Please set the tag or branch in messenger.json manually.")
        os.chdir("..")

        if os.path.exists(SCENEPROTO_DIR):
            self.__update_scene(SCENEPROTO_DIR, True)
        if not os.path.exists(SCENE_DIR):
            os.mkdir(SCENE_DIR)
        self.__update_scene(SCENE_DIR, False)
        self.dump_config()

    def __update_scene(self, sceneDir: str, isProto: bool):
        field = "sceneprotos" if isProto else "scenes"
        for sceneName in sorted(os.listdir(sceneDir), key=lambda d: os.path.join(sceneDir, d)):
            if os.path.isdir(os.path.join(sceneDir, sceneName)):
                scene = os.path.join(sceneDir, sceneName)
                if not os.path.exists(os.path.join(scene, "Model.elm")):
                    continue
                self.config[field][sceneName] = {}
                with open(os.path.join(scene, "Model.elm"), "r") as f:
                    content = f.read()
                    if not isProto and "LevelInit" in content:
                        pattern = r'import SceneProtos\.(\w+)\.Model'
                        match = re.search(pattern, content)
                        if match:
                            self.config[field][sceneName]["sceneproto"] = match.group(1)
                            self.config["sceneprotos"][match.group(1)]["levels"].append(sceneName)
                    self.config[field][sceneName]["raw"] = "import Messenger.Scene.RawScene" in content
                if isProto:
                    self.config[field][sceneName]["levels"] = []
                    
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
        if self.config["auto_commit"]:
            execute_cmd(f"git add {SCENE_DIR}/{name}")

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
            if self.config["auto_commit"]:
                execute_cmd(f"git add {SCENEPROTO_DIR}/{scene}")
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
                execute_cmd(f"git add {SCENE_DIR}/{scene}")

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
            execute_cmd(f"git add {SCENE_DIR}/AllScenes.elm")

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
                execute_cmd(f"git add {GC_DIR}/{name}")
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
                if self.config["auto_commit"]:
                    execute_cmd(f"git add {SCENEPROTO_DIR}/{scene}/SceneBase.elm")

            if not os.path.exists(f"{SCENEPROTO_DIR}/{scene}/{dir}/ComponentBase.elm"):
                Updater(
                    [".messenger/component/ComponentBase.elm"],
                    [f"{SCENEPROTO_DIR}/{scene}/{dir}/ComponentBase.elm"],
                ).rep("SceneProtos").rep(scene).rep(dir)
                if self.config["auto_commit"]:
                    execute_cmd(f"git add {SCENEPROTO_DIR}/{scene}/{dir}/ComponentBase.elm")

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
            if self.config["auto_commit"]:
                execute_cmd(f"git add {SCENEPROTO_DIR}/{scene}/{dir}/{name}")
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
                if self.config["auto_commit"]:
                    execute_cmd(f"git add {SCENE_DIR}/{scene}/{dir}/ComponentBase.elm")

            if not os.path.exists(f"{SCENE_DIR}/{scene}/SceneBase.elm"):
                Updater(
                    [".messenger/scene/SceneBase.elm"],
                    [f"{SCENE_DIR}/{scene}/SceneBase.elm"],
                ).rep(scene)
                if self.config["auto_commit"]:
                    execute_cmd(f"git add {SCENE_DIR}/{scene}/SceneBase.elm")

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
                execute_cmd(f"git add {SCENE_DIR}/{scene}/{dir}/{name}")

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
                if self.config["auto_commit"]:
                    execute_cmd(f"git add {SCENEPROTO_DIR}/{scene}/{dir}/ComponentBase.elm")

            if not os.path.exists(f"{SCENEPROTO_DIR}/{scene}/SceneBase.elm"):
                Updater(
                    [".messenger/sceneproto/SceneBase.elm"],
                    [f"{SCENEPROTO_DIR}/{scene}/SceneBase.elm"],
                ).rep(scene)
                if self.config["auto_commit"]:
                    execute_cmd(f"git add {SCENEPROTO_DIR}/{scene}/SceneBase.elm")
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
            if self.config["auto_commit"]:
                execute_cmd(f"git add {SCENEPROTO_DIR}/{scene}/{layer}")
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
                if self.config["auto_commit"]:
                    execute_cmd(f"git add {SCENE_DIR}/{scene}/{dir}/ComponentBase.elm")

            if not os.path.exists(f"{SCENE_DIR}/{scene}/SceneBase.elm"):
                Updater(
                    [".messenger/scene/SceneBase.elm"],
                    [f"{SCENE_DIR}/{scene}/SceneBase.elm"],
                ).rep(scene)
                if self.config["auto_commit"]:
                    execute_cmd(f"git add {SCENE_DIR}/{scene}/SceneBase.elm")
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
                execute_cmd(f"git add {SCENE_DIR}/{scene}/{layer}")

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


@app.command()
def init(
    name: str,
    template_repo=typer.Option(
        "https://github.com/linsyking/messenger-templates",
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
):
    execute_cmd("elm")
    execute_cmd("elm-format")
    input(
        f"""Thanks for using Messenger.
See https://github.com/linsyking/Messenger for more information.
Here is my plan:

- Create a directory named {name}
- Install the core Messenger library
- Install the elm packages needed

Press Enter to continue
"""
    )
    os.makedirs(name, exist_ok=True)
    os.chdir(name)
    print("Cloning templates...")
    if template_tag:
        execute_cmd(f"git clone -b {template_tag} {template_repo} .messenger --depth=1")
    else:
        template_tag = ""
        execute_cmd(f"git clone {template_repo} .messenger --depth=1")
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
        print("Adding files to git...")
        execute_cmd("git add ./src")
        execute_cmd("git add ./public/elm-audio.js ./public/elm-messenger.js ./public/style.css")
        execute_cmd("git add ./public/index.html")
        execute_cmd("git add ./.gitignore ./Makefile ./elm.json")
        execute_cmd("git add ./assets/fonts")
        execute_cmd("git add ./messenger.json")
        if not use_cdn:
            execute_cmd("git add ./public/regl.js")
        print("Making git commit...")
        execute_cmd("git commit -m 'build(Messenger): initialize project'")
    print("Done!")
    print(f"Now please go to {name} and add scenes and components.")


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
def update():
    msg = Messenger()
    input(
        f"You are going to update messenger.json according to your project, continue?"
    )
    msg.update_config()
    msg.format()
    if msg.config["auto_commit"]:
        execute_cmd(
            "git commit -m 'build(Messenger): update messenger.json'"
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
    range=typer.Option(4, "--range", help="Set the distance range."),
):
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



if __name__ == "__main__":
    app()
