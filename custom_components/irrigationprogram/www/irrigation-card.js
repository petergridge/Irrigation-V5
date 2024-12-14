class IrrigationCard extends HTMLElement {


  setConfig(config) {
    if (this.lastChild) this.removeChild(this.lastChild);
    const cardConfig = Object.assign({}, config);
    if (!cardConfig.card) cardConfig.card = {};
    if (!cardConfig.card.type) cardConfig.card.type = "entities";
     if (!cardConfig.entities_vars)
       cardConfig.entities_vars = { type: "entity" };
    const element = document.createElement('hui-entities-card');
    this._config = JSON.parse(JSON.stringify(cardConfig));
    customElements.whenDefined("card-mod").then(() => {
      customElements
        .get("card-mod")
        .applyToElement(element, "card-mod-card", this._config.card_mod.style);
    });

    this.appendChild(element);
  }

  set hass(hass) {

    const config = this._config;
    config.card.title = config.title;
    //https://www.home-assistant.io/lovelace/header-footer/
    config.card.header = config.header;
    config.card.footer = config.footer;
    config.card.icon = config.icon;
    config.card.theme = config.theme;
    config.card.show_header_toggle = false;
    config.card.state_color = true;
    let doErrors = [];
    let validconfig = "invalid";

    let zones = hass.states[config.program].attributes["zones"];

    let entities = [];

    console.log("editor:constructor()");

    const x = hass.states[config.program];
    if (!x) {
      config.card.title = "ERR";
      validconfig == "invalid";
      doErrors.push({
        type: "section",
        label: "Program: not found",
      });
      config.card.title = "ERROR: " + config.program;
    } else {
      validconfig = "valid";
    }

    if (validconfig === "valid") {
      if (!hass.states[config.program].attributes["zones"]) {
        doErrors.push({
          type: "section",
          label: "Program: not v2024.11 or newer irriation component",
        });
        config.card.title = "ERROR: " + config.program;
        validconfig = "invalid";
      }
    }

    function doRenderProgram(hass) {

      // Build the Card
      if (config.show_program === true) {
        let showconfig = hass.states[config.program].attributes["show_config"]

        var buttons = [];
        buttons.length = 0;
        //Add button group
        buttons.push({
          entity: config.program,
          show_name: true,
        });
        buttons.push({
          entity: showconfig,
          show_name: true,
        });
        var condition = [{ entity: config.program, state: "off" }];
        entities.push({
          type: "conditional",
          conditions: condition,
          row: {
            type: 'buttons',
            entities: buttons
          }
        });

        var buttons1 = [];
        buttons1.length = 0;
        buttons1.push({
          entity: config.program,
          show_name: true,
        });
        buttons1.push({
          entity: showconfig,
          show_name: true,
        });
        buttons1.push({
          entity: hass.states[config.program].attributes["pause"],
          show_name: false,
        });
        var condition = [{ entity: config.program, state: "on" }];
        entities.push({
          type: "conditional",
          conditions: condition,
          row: {
            type: 'buttons',
            entities: buttons1
          }
        });

        var condition = [{ entity: config.program, state_not: "on" },{ entity: showconfig, state_not: "on" }];
        add_simple_entity(config.program, condition, "start_time", entities);

        var condition = [{ entity: showconfig, state: "on" }];
        if (hass.states[config.program].attributes["sunrise"] || hass.states[config.program].attributes["sunset"]) {
          add_simple_entity(config.program, condition, "start_time", entities);
        } else {
          add_entity(config.program, condition, "start_time", entities);
        }
        add_entity(config.program,condition, "sunrise", entities);
        add_entity(config.program,condition, "sunset", entities);

        var condition = [{ entity: config.program, state: "on" }];
        add_entity(config.program, condition, "remaining", entities);

        var condition = [{ entity: showconfig, state: "on" }];
        add_entity(config.program, condition, "irrigation_on", entities);
        add_entity(config.program, condition, "run_freq", entities);
        add_entity(config.program, condition, "inter_zone_delay", entities);
      }

      //add the zones
      zones = config.entities;

      let first_zone = true;
      let i, len;
      for (i = 0; len = zones.length, i < len; i++) {
        let zone = zones[i]
        AddZone(zone, first_zone);
        first_zone = false;
      };

      return entities;

      function add_entity(object, conditions = [], entity, array) {
        if (hass.states[object].attributes[entity]) {
          array.push({
            type: "conditional",
            conditions: conditions,
            row: {
              entity: hass.states[object].attributes[entity]
            },
          });
        }
      } //add_entity

      function add_simple_entity(object, conditions = [], entity, array) {
        if (hass.states[object].attributes[entity]) {
          array.push({
            type: "conditional",
            conditions: conditions,
            row: {
              entity: hass.states[object].attributes[entity],
              type: "simple-entity"
            },
          });
        }
      } //add_entity

      // Process zone
      function AddZone(zone, first_zone) {

        //Add a section break
        if (config.show_program === false && first_zone && !config.title) {
          //do nothing
        } else {
          entities.push({ type: "section", label: "" });
        }

        let showconfig = hass.states[zone].attributes["show_config"]

        let btns1 = [];
        btns1.length = 0
        //Add the buttons
        btns1.push({
          entity: zone,
          show_name: true,
          show_icon: false,
          tap_action: {
            action: "call-service",
            service: "switch.toggle",
            service_data: {
              entity_id: zone,
            },
          },
        });

        btns1.push({
          entity: showconfig,
          show_name: false,
        });

        var condition = [{ entity: hass.states[zone].attributes["status"], state: "off" }];
        entities.push({
          type: "conditional",
          conditions: condition,
          row: {
            type: 'buttons',
            entities: btns1
          }
        });

        let btns = [];
        btns.length = 0
        //Add the buttons
        btns.push({
          entity: zone,
          show_name: true,
          show_icon: false,
          tap_action: {
            action: "call-service",
            service: "switch.toggle",
            service_data: {
              entity_id: zone,
            },
          },
        });

        btns.push({
          entity: showconfig,
          show_name: false,
        });

        btns.push({
          entity: hass.states[zone].attributes["status"],
          show_name: false,
        });

        var condition = [{ entity: hass.states[zone].attributes["status"], state_not: "off" }];
        entities.push({
          type: "conditional",
          conditions: condition,
          row: {
            type: 'buttons',
            entities: btns
          }
        });


        let zonestatus = hass.states[zone].attributes["status"]

        var condition = [{ entity: zonestatus, state: ["off"]}        ]
        add_entity(zone, condition, "next_run", entities)

        condition = [{ entity: zonestatus, state_not: ["off", "on", "pending", "eco"]}        ]
        add_entity(zone, condition, "status", entities)

        condition = [{ entity: zonestatus, state: ["on","eco","pending"]}        ]
        add_entity(zone, condition, "remaining", entities)

        condition = [
          { entity: zonestatus, state_not: ["on", "eco", "pending"] },
          { entity: showconfig, state: "on" },
        ]
        add_entity(zone, condition, "last_ran", entities)

        condition = [{ entity: showconfig, state: "on" }]
        add_entity(zone, condition, "enable_zone", entities)
        add_entity(zone, condition, "run_freq", entities)
        add_entity(zone, condition, "water", entities)
        add_entity(zone, condition, "wait", entities)
        add_entity(zone, condition, "repeat", entities)
        add_entity(zone, condition, "flow_sensor", entities)
        add_entity(zone, condition, "water_adjustment", entities)
        add_entity(zone, condition, "rain_sensor", entities)
        add_entity(zone, condition, "water_source_active", entities)
        add_entity(zone, condition, "ignore_sensors", entities)
      } //AddZone

      //------------------------------------------------------------

    } //doRenderProgram

    if (validconfig === "valid") {
      config.card.entities = doRenderProgram(hass);
    } else {
      config.card.entities = doErrors;
    }

    this.lastChild.setConfig(config.card);
    this.lastChild.hass = hass;
  }

  static getConfigElement() {
    return document.createElement("irrigation-card-editor");
  }

  static getStubConfig() {
    return {
      program: "",
      entities: [],
      show_program: true,
    };
  }

  getCardSize() {
   return "getCardSize" in this.lastChild ? this.lastChild.getCardSize() : 1;
  }
}

class IrrigationCardEditor extends HTMLElement {
  // private properties
  _config;
  _hass;
  _elements = {};

  // lifecycle
  constructor() {
    super();
    console.log("editor:constructor()");
    this.doEditor();
    this.doStyle();
    this.doAttach();
    this.doQueryElements();
    this.doListen();
  }

  setConfig(config) {
    console.log("editor:setConfig()");
    this._config = config;
    this.doUpdateConfig();
  }

  set hass(hass) {
    console.log("editor.hass()");
    this._hass = hass;
    this.doUpdateHass();
  }

  onChanged(event) {
    console.log("editor.onChanged()");
    this.doMessageForUpdate(event);
  }

  // jobs
  doEditor() {
    this._elements.editor = document.createElement("form");
    this._elements.editor.innerHTML = `
			<div class="row"><label class="label" for="program">Program:</label><select class="value" id="program" ></select></div>
			<div class="row"><label class="label" for="entities">Zone:</label><select class="value" id="entities" size=10 multiple></select></div>
			<div class="row"><label class="label" for="show_program">Show program:</label><input type="checkbox" id="show_program" checked></input></div>
			`;
  }

  doStyle() {
    this._elements.style = document.createElement("style");
    this._elements.style.textContent = `
              form {
                  display: table;
              }
              .row {
                  display: table-row;
              }
              .label, .value {
                  display: table-cell;
                  padding: 0.5em;
              }
          `;
  }

  doAttach() {
    this.attachShadow({ mode: "open" });
    this.shadowRoot.append(this._elements.style, this._elements.editor);
  }

  doQueryElements() {
    this._elements.program = this._elements.editor.querySelector("#program");
    this._elements.entities = this._elements.editor.querySelector("#entities");
    this._elements.show_program =
      this._elements.editor.querySelector("#show_program");
  }

  doListen() {
    this._elements.program.addEventListener(
      "change",
      this.onChanged.bind(this)
    );
    this._elements.entities.addEventListener(
      "change",
      this.onChanged.bind(this)
    );
    this._elements.show_program.addEventListener(
      "change",
      this.onChanged.bind(this)
    );
  }

  doBuildProgramOptions(program) {
    // build the list of available programs
    var select = this._elements.program;
    // remove the existing list
    var i = 0;
    var l = select.options.length - 1;
    for (i = l; i >= 0; i--) {
      select.remove(i);
    }

		//if new card
		if ( this._config.program.length == 0 ) {
			let x = "           "
			let newOption = new Option(x, x);
			select.add(newOption);
		}

    // populate the list of programs
    for (var x in this._hass.states) {
      if (this._hass.states[x].attributes["attribution"] ==  "Irrigation Program") {
        var friendly_name = this._hass.states[x].attributes["friendly_name"];
        let newOption = new Option(friendly_name, x);

        if (x == this._config.program) {
          newOption.selected = true;
        }
        select.add(newOption);
      }
    }

  }

  doBuildEntityOptions(program, entities) {
    // build the list of zones in the program
    console.log("do build entity options")
    //var zones = Number(this._hass.states[program].attributes["zone_count"]);
    var select = this._elements.editor.querySelector("#entities");
    //remove existing options
    var zones = this._hass.states[program].attributes["zones"];
    var l = zones.length;
    var i = 0;

    for (i = l; i >= 0; i--) {
      console.log("do build entity options - remove")
      select.remove(i);
    }

    for (i = 0; i < l; i++) {
      var zone = zones[i]
      var friendly_name = this._hass.states[zone].attributes["friendly_name"];
      var zone_name = this._hass.states[zone].entity_id;

      let newOption = new Option(friendly_name,zone_name);
      if (entities.includes(zone_name)) {
        newOption.selected = true;
      }
      select.add(newOption);
    }
  }

  doUpdateConfig() {
    // Build values on load
    this.doBuildProgramOptions(this._config.program);
    this._elements.show_program.checked = this._config.show_program;
    if (this._elements.program.value.split(".")[0] == "switch") {
      this._elements.entities.value = this._hass.config["entities"];
      this.doBuildEntityOptions(
        this._elements.program.value,
        this._config.entities
      );
    }
  }

  doUpdateHass() {}

  doMessageForUpdate(changedEvent) {
    // Update values on change the event

    // this._config is readonly, copy needed
    const newConfig = Object.assign({}, this._config);

    if (changedEvent.target.id == "program") {
      // get the selected program
      var selected = this._elements.editor.querySelector("#program");
			this._elements.entities.value = [];
			newConfig.entities = [];
 			newConfig.program = selected.value;
    } else if (changedEvent.target.id == "entities") {
      // format the list of selected zones
      var selectedentities = [];
      var count = 0;
      var select = this._elements.editor.querySelector("#entities");
      for (var i = 0; i < select.options.length; i++) {
        if (select.options[i].selected) {
          selectedentities[count] = select.options[i].value;
          count++;
        }
      }
      newConfig.entities = selectedentities;
    } else if (changedEvent.target.id == "show_program") {
      newConfig.show_program = changedEvent.target.checked;
    }

    const event = new Event("config-changed", {
      bubbles: true,
      composed: true,
    });
		event.detail = { config: newConfig };
    this.dispatchEvent(event);
  }
}

customElements.define("irrigation-card-editor", IrrigationCardEditor);
customElements.define("irrigation-card", IrrigationCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "irrigation-card",
  name: "Irrigation Card",
  preview: true, // Optional - defaults to false
  description: "Custom card companion to Irrigation Custom Component", // Optional
});