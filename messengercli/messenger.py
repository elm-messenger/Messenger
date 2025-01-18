#!/usr/bin/env python3

import typer
import os
import shutil
import json
from .updater import Updater

app = typer.Typer(add_completion=False, help="Messenger CLI")
API_VERSION = "1.2.0"

SCENE_DIR = "src/Scenes"
SCENEPROTO_DIR = "src/SceneProtos"


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
                os.system(f"git clone {repo["url"]} .messenger --depth=1")
            else:
                os.system(
                    f"git clone -b {repo["tag"]} {repo["url"]} .messenger --depth=1"
                )

    def dump_config(self):
        with open("messenger.json", "w") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def update_config(self):
        self.config["scenes"] = {}
        self.config["sceneprotos"] = {}

        self.__update_scene(SCENE_DIR, False)
        if os.path.exists(SCENEPROTO_DIR):
            self.__update_scene(SCENEPROTO_DIR, True)
        self.dump_config()

    def __update_scene(self, sceneDir: str, isProto: bool):
        field = "sceneprotos" if isProto else "scenes"
        initScene = lambda x: (
            {"raw": x}
            if isProto
            else {}
        )
        for sceneName in os.listdir(sceneDir):
            if os.path.isdir(os.path.join(sceneDir, sceneName)):
                scene = os.path.join(sceneDir, sceneName)
                if os.path.exists(os.path.join(scene, "Model.elm")):
                    with open(os.path.join(scene, "Model.elm"), "r") as f:
                        raw = "genRawScene" in f.read()
                else:
                    continue
                if (
                    isProto
                    or raw
                    or os.path.exists(os.path.join(scene, "SceneBase.elm"))
                ):
                    self.config[field][sceneName] = initScene(raw)
                else:
                    self.config[field][sceneName] = []

    def add_level(self, name: str, sceneproto: str):
        """
        Add a level
        """
        if sceneproto not in self.config["sceneprotos"]:
            raise Exception("Sceneproto doesn't exist.")
        if name in self.config["scenes"]:
            raise Exception("Level or scene already exists.")
        self.config["scenes"][name] = {
            "sceneproto": sceneproto,
            "raw": self.config["sceneprotos"][sceneproto]["raw"]
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

    def update_scenes(self):
        """
        Update scene settings (AllScenes and SceneSettings)
        """
        scenes = self.config["scenes"]
        Updater([".messenger/scene/AllScenes.elm"], [f"{SCENE_DIR}/AllScenes.elm"]).rep(
            "\n".join([f"import Scenes.{l}.Model as {l}" for l in scenes])
        ).rep(",\n".join([f'( "{l}", {l}.scene )' for l in scenes]))

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

    def format(self):
        os.system("elm-format src/ --yes")

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
    use_cdn : bool =typer.Option(
        False,
        "--use-cdn",
        help="Use jsdelivr CDN for elm-regl JS file.",
    ),
    minimal : bool =typer.Option(
        False,
        "--min",
        help="Use minimal regl JS that has no builtin font.",
    ),
):
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
    if template_tag:
        os.system(f"git clone -b {template_tag} {template_repo} .messenger --depth=1")
    else:
        template_tag = ""
        os.system(f"git clone {template_repo} .messenger --depth=1")
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

    os.makedirs(f"{SCENE_DIR}", exist_ok=True)
    os.makedirs("assets", exist_ok=True)

    print("Creating elm.json...")
    initObject = {
        "version": API_VERSION,
        "template_repo": {
            "url": template_repo,
            "tag": template_tag,
        },
        "scenes": {},
        "sceneprotos": {},
    }
    with open("messenger.json", "w") as f:
        json.dump(initObject, f, indent=4, ensure_ascii=False)
    print("Installing dependencies...")
    os.system("elm make")
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
    msg.add_component(name, scene, compdir, is_proto, init)
    msg.format()
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
    msg.add_scene(name, raw, is_proto, init)
    msg.update_scenes()
    msg.format()
    print("Done!")


@app.command()
def level(sceneproto: str, name: str):
    name = check_name(name)
    sceneproto = check_name(sceneproto)
    msg = Messenger()
    input(
        f"You are going to create a level named {name} from sceneproto {sceneproto}, continue?"
    )
    msg.add_level(name, sceneproto)
    msg.update_scenes()
    msg.format()
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
    msg.add_layer(scene, layer, has_component, is_proto, compdir, init)
    msg.format()
    print("Done!")


@app.command()
def update():
    msg = Messenger()
    input(
        f"You are going to update messenger.json according to your project, continue?"
    )
    msg.update_config()
    msg.format()
    print("Done!")


@app.command()
def remove(
    type: str,
    name: str,
    remove: bool = typer.Option(False, "--rm", help="Also remove the modules."),
    remove_levels: bool = typer.Option(False, "--rml", help="Remove all levels in the sceneproto."),
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
                raise Exception("There are levels using the sceneproto. Please remove them first.")
        msg.config["sceneprotos"].pop(name)
        if remove:
            shutil.rmtree(f"{SCENEPROTO_DIR}/{name}")
    else:
        print("No such type.")
    msg.dump_config()


if __name__ == "__main__":
    app()
