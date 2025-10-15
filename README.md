<h1><img height="25" style="max-height:25px;" src="https://dynabic.eu/wp-content/uploads/2023/02/logo.png"/> CTI4BC (CTI for Business Continuity)</h1>


## Introduction

Collection of core functionalities to work with Information sharing (IS) and Cyber threat Intelligence  (CTI) platforms for the Dynabic components.

The selected IS for this project is is [MISP](https://www.misp-project.org/) for all project partners, so we can share/refine/test functionalities useful to everyone, saving time in the process...  

CTI4BC is a component for the [Dynabic (UE Horizon Europe) project](https://dynabic.eu/).

<img src="./media/cti-misp_event.png"/>

## Zen design

- Keep everything **simple**. Every contributor has their own coding preferences. Let minimize mandatory type structures, paradigms and so on.
- Minimal config (broker, misp access). This repo should be treated as a `library`. Other Dynabic services will be provided from a common DNS root prefix (TBD).
- Small list of **dependencies**. We do not need to add devops or build layer. Maintenance time could be spent on new lib features and not in dependency management and updates.

## Installation

```
# Download or clone repo
git clone https://gitlab.com/dynabic/cti4bc

# Install as *development* package
# This will install aiohttp and pytest packages
pip install -e "./cti4bc/src"

# Optional, create a virtual env
# Optional, installation using $PYTHONPATH
```

##  Configuration
 
- Option a - Using environment variables. *This should be the preferred way for contributors to the core lib*. The library requires url and misp api key. The recommended approach is to add them to the environment variables `MISP_URL` and `MISP_TOKEN` (in /etc/environment or .env file or activate file, etc), but it is up to the user to set these credentials in env or when calling the `misp.configure(url, key)` method. For risk related features set `RISK_URL` `RISK_TOKEN`.
- Option b - Using explicit `configure(url,token)` method. *This should be the preferred way for external consumers of the core lib*. When starting application we can set/override the endpoints by calling the configure() method on some modules.

> Note: create an API key from your MISP instance. We can **temporary** provide a key for DYNABIC partners in case no MISP server yet. 

Example of configuration parameters:

```
MISP_TOKEN="kajeucn09876njeudnenSAFBXxs"
MISP_URL="https://misp.example.com"
RISK_URL="https://risk.example.com"
RISK_TOKEN='82jeNajeucneDsxzyq'
```

## Usage

> Note: this lib uses the asyncio library for I/O tasks. The async/await paradigm will be very useful on development, because most of the library features are wiring services. 

- **Contributors** to the lib: clone from repo. Each module will have *one owner*. Others can contribute to any module, but be in contact with owner. `Test` folder: implement only critical tests, we are in alpha stage and not all features will be at production-level quality. To run tests execute command `pytest` in a terminal. Some test files can contain asserts, others can have only functionality and wait for the code to raise errors. 

- **External** (or external+internal) developers: See how to use [in the cti4bc-example](/cti4bc-example/main.py) folder. Install either setting  the `$PYTHONPATH` or install as local package with `pip install -e`.

- **Standalone app** only for the development phase. The library is started as a server by using the `main.py` file. Useful for pushing incoming incidents from other MISP instances into the CTI4BC component. 

Example (see tests folder for more examples):

```py
import asyncio
import cti4bc.misp as misp
# (or) from cti4bc import misp

async def main():
    try:
      # Optional
      # misp.configure(url,api_key)
      events = await misp.event.list()
      id = events[0]['id']
      event = await misp.event.get(id)
      print(event)
    except Exception as e:
      # handle e.code, e.status
      print(e)

asyncio.run(main())

```

### Tips on VSCODE (Only for non-default VSCODE)

The simplest approach is to install the lib as development package (and described above) and start the VSCODE from the installation folder. The run/debug buttons and autocomplete should work.

Alternatively, there are some reasons for other development paths. For instance, people who want to add the project as a subfolder (not in the VSCODE workspace and not as root folder), people who want this and other packages to be treated as folders and not installed by pip, or for any other reasons. In these cases, VSCODE cannot find the package and `Debug` or `Autocomplete (intellisense)` when typing will not be available. The additional configuration steps are:

- For run/debug: to find the modules in run/debug/ or terminal, add PYTHONPATH to the environment. For instance, if a virtualenv is used, add this to the `.venv/bin/activate`. Then restart VSCODE or open a new terminal, or reactivate the venv to get the changes. PYTHONPATH is similar to the classpath in Java, where the code can be found and executed with no installation steps.
```sh
PYTHONPATH="$PYTHONPATH:/YOUR/DYNABIC/FOLDER/cti4bc/src"
export PYTHONPATH
``` 
- For autocomplete/intellisense: add to settings.json (in the user, workspace or folder) the following property:
```json
  "python.analysis.extraPaths": [
    "/YOUR/DYNABIC/FOLDER/cti4bc/src"
  ]
``` 

## Modules in the library

### skeletons

Data Types with default values. So everyone can put a curated skeleton there and rest of developers do not need to understand the object, just get a copy and update 1 or 2 fields. Since Python is not a compiled, strict-typing language, let's prioritize productivity. Work with simple objects, and when a complex one is really required, put it in the skeletons list.

### misp

Minimal set of actions to interact with MISP servers. See `API` navigation tab in your MISP instance (Note: this module is not intended to be an autogenerated OpenAPI with all services and models. We will spent more time dealing with Dynabic data-models...).

### risk
Two use cases: 

- internal incident in the critical infrastructure: CTI4BC adds automatically risk information in the MISP event. The operator can visualize different aspects of the incident, from the security pont of view, but also from the risk perspective of the business. Currently, an endpoint to the RISK service is provided encapsulated into a MISP attribute.

<img src="./media/cti-risk-info.png"/>

- external incident from another critical infrastructure: the incident may affect this infrastructure. Therefore,relevant info is notified to the risk system, in order to evaluate whether the external incident may cause a potential disruption in our infrastructure in the near future.

<img src="./media/cti-incoming-incident.png"/>


### enrich

Two-way enrichment: the core components in the backend allow enriching data from incoming events shared by external Information Sharing platforms, to add more metadata to the local MISP instance. On the other hand, CTI4BC can provide richer infomation to an event, while preserving anonymized data, before sharing an incident.

From external incidents arriving to CTI4BC: the entry point for these incidents is the local MISP instance whic is connected to external Information Sharing peers. The current enrichment is performed by providing the risk module relevant information about the external incident in order for the module to retrieve advanced feedback from RISK4BC about how the external incident my affect our internal critical infrastructure.

From internal incidents: CTI4BC can automatically request other DYNABIC tools for more information, or periodically update the current status of the incident. This extra information (ticket incident status, changes in even tag to critical provided by the continous risk assesment, etc.) can help CTI operator to take the final decision of sharing the incident to other relevant peers. CTI4BC currently acts on the enrich() method in the MISP module to perform this task.


### anonymization, gather feeds, post-process, etc

TBD

## TODO list
- [x] Test: update: PyTest may fit better than Unittest. We require to install another dependency, but it is the simplest way for beginners or experts in testing.
- [ ] Types: keep simple types and Dictionaries (JSON-like), complex but general-usage objects should be retrieved by skeletons. Custom types are allowed internally on each module.

## Acknowledgements

*This project has received funding from the European Union’s Horizon Europe research and innovation programme under grant agreement No 101070455.*

Dynabic (UE Horizon Europe) project](https://dynabic.eu/)
