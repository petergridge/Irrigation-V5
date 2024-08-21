class IrrigationCard extends HTMLElement {


  setConfig(config) {
    if (this.lastChild) this.removeChild(this.lastChild);
    const cardConfig = Object.assign({}, config);
    if (!cardConfig.card) cardConfig.card = {};
    if (!cardConfig.card.type) cardConfig.card.type = "entities";
    if (!cardConfig.entities_vars)
      cardConfig.entities_vars = { type: "entity" };
    const element = document.createElement(`hui-${cardConfig.card.type}-card`);
    this._config = JSON.parse(JSON.stringify(cardConfig));
    customElements.whenDefined("card-mod").then(() => {
      customElements
        .get("card-mod")
        .applyToElement(element, "card-mod-card", this._config.card_mod.style);
    });

    this.appendChild(element);
  }

  set hass(hass) {
    let entities = [];

    const config = this._config;
    config.card.title = config.title;
    //https://www.home-assistant.io/lovelace/header-footer/
    config.card.header = config.header;
    config.card.footer = config.footer;
    config.card.icon = config.icon;
    config.card.theme = config.theme;
    config.card.show_header_toggle = false;
    config.card.state_color = true;
    let defentities = [];
    let validconfig = "invalid";

    let zones = Number(hass.states[config.program].attributes["zone_count"]);

    const x = hass.states[config.program];
    if (!x) {
      config.card.title = "ERR";
      validconfig == "invalid";
      defentities.push({
        type: "section",
        label: "Program: not found",
      });
      config.card.title = "ERROR: " + config.program;
    } else {
      validconfig = "valid";
    }

    if (validconfig === "valid") {
      if (!hass.states[config.program].attributes["zone_count"]) {
        defentities.push({
          type: "section",
          label: "Program: not v4 or newer irriation component",
        });
        config.card.title = "ERROR: " + config.program;
        validconfig = "invalid";
      }
    }

    function cardentities(hass, program) {
      function addZoneRunConfigButtons(p_zone, p_config) {
        var zone_name = hass.states[p_zone].attributes["friendly_name"];
//        var zone_name = "test";
        var buttons = [];
        buttons[0] = {
          entity: p_zone,
          name: zone_name,
          icon: "mdi:water",
          tap_action: {
            action: "call-service",
            service: "irrigationprogram.toggle_zone",
            service_data: {
              entity_id: config.program,
              zone: p_zone,
            },
          },
        };

        buttons[1] = {
          entity: p_config,
          show_name: false,
          tap_action: {
            action: "call-service",
            service: "irrigationprogram.toggle",
            service_data: {
              entity_id: p_config,
            },
          },
        };

        entities.push({
          type: "buttons",
          entities: buttons,
        });
      } //addZoneRunConfigButtons

      function addProgramRunConfigButtons() {
        var buttons = [];
        let showconfig = hass.states[config.program].attributes["show_config"];
        buttons[0] = {
          entity: config.program,
          show_name: true,
          icon: "mdi:power",
        };

        buttons[1] = {
          entity: showconfig,
          show_name: false,
          tap_action: {
            action: "call-service",
            service: "irrigationprogram.toggle",
            service_data: {
              entity_id: showconfig,
            },
          },
        };

        entities.push({
          type: "buttons",
          entities: buttons,
        });
      } //addProgramRunConfigButtons

      function add_entity(p_conditions = [], p_entity, array) {
        if (hass.states[config.program].attributes[p_entity]) {
          array.push({
            type: "conditional",
            conditions: p_conditions,
            row: { entity: hass.states[config.program].attributes[p_entity] },
          });
        }
      } //add_entity

      function add_attribute(p_attribute, p_name, p_icon, p_conditions, array) {
        if (hass.states[config.program].attributes[p_attribute]) {
          array.push({
            type: "conditional",
            conditions: p_conditions,
            row: {
              type: "attribute",
              entity: config.program,
              attribute: p_attribute,
              format: "relative",
              name: p_name,
              icon: p_icon,
              state_color: false,
            },
          });
        }
      } //add_attribute

      function has_attr_value(p_attribute) {
        let attrvalue = null;
        if (hass.states[config.program].attributes[p_attribute]) {
          attrvalue = hass.states[config.program].attributes[p_attribute];
        }
        return attrvalue;
      } //has_attr_value

      function add_attr_value(p_attribute, array,showconfig) {
        if (has_attr_value(p_attribute)) {
          add_entity([{ entity: showconfig, state: "on" }], p_attribute, array);
        }
      } //add_attr_value

      function ProcessZone(zone, zone_attrs) {
        let pname = zone.split(".")[1];
        let showconfig = hass.states[config.program].attributes[pname + "_show_config"];
        //let zonestatus =
        //  hass.states[config.program].attributes[parentname + "_status"];

        // list of other in order
        add_attr_value(pname + "_enable_zone", zone_attrs,showconfig);
        add_attr_value(pname + "_run_freq", zone_attrs, showconfig);
        add_attr_value(pname + "_water", zone_attrs, showconfig);
        add_attr_value(pname + "_water_adjustment", zone_attrs, showconfig);
        add_attr_value(pname + "_flow_sensor", zone_attrs, showconfig);
        add_attr_value(pname + "_wait", zone_attrs, showconfig);
        add_attr_value(pname + "_repeat", zone_attrs, showconfig);
        add_attr_value(pname + "_rain_sensor", zone_attrs, showconfig);
        add_attr_value(pname + "_ignore_rain_sensor", zone_attrs, showconfig);
      } //ProcessZone


      function ZoneHeader(zone, zone_name, first_zone) {

        let name = zone.split(".")[1];
        // process zone/zonegroup main section
        let zonestatus =
          hass.states[config.program].attributes[zone_name + "_status"];
        if (config.show_program === false && first_zone && !config.title) {
          //do nothing
        } else {
          entities.push({ type: "section", label: "" });
        }

        let showconfig =
          hass.states[config.program].attributes[zone_name + "_show_config"];
        addZoneRunConfigButtons(zone, showconfig);

        // var llocale = window.navigator.userLanguage || window.navigator.language;
        // if (config.hass_lang_priority) {
        //   llocale = this.myhass.language;
        // }
        // var translationJSONobj = null;

        // var translationLocal = "/local/" + llocale.substring(0, 2) + ".json";
        // var rawFile = new XMLHttpRequest();
        // rawFile.overrideMimeType("application/json");
        // rawFile.open("GET", translationLocal, false);
        // rawFile.send(null);
        // if (rawFile.status == 200) {
        //   translationJSONobj = JSON.parse(rawFile.responseText);
        // } else {
        //   // if no language file found, default to en
        //   translationLocal = "/local/en.json";
        //   rawFile.open("GET", translationLocal, false);
        //   rawFile.send(null);
        //   if (rawFile.status == 200) {
        //     translationJSONobj = JSON.parse(rawFile.responseText);
        //   } else {
        //     translationJSONobj = null;
        //   }
        // }

        // var remaining_lable = "remaining"
        // if (typeof translationJSONobj != null) {
        //    remaining_lable = translationJSONobj.other['remaining'] + " ";
        // }

        // Show the remaining time when on/eco/pending
        add_attribute(
          zone_name + "_remaining",
          config.remaining_label || "Remaining Time",
          "mdi:timer-outline",
          [
            { entity: zonestatus, state: "on" },
          ],
          entities
        );
        add_attribute(
          zone_name + "_remaining",
          config.remaining_label || "Remaining Time",
          "mdi:timer-outline",
          [
            { entity: zonestatus, state: "pending" },
          ],
          entities
        );
        add_attribute(
          zone_name + "_remaining",
          config.remaining_label || "Remaining Time",
          "mdi:timer-outline",
          [
            { entity: zonestatus, state: "eco" },
          ],
          entities
        );
        // Next/Last run details
        add_attribute(
          zone_name + "_next_run",
          config.next_run_label || "Next Run",
          "mdi:clock-start",
          [
            { entity: zonestatus, state_not: "on" },
            { entity: zonestatus, state_not: "eco" },
            { entity: zonestatus, state_not: "pending" },
          ],
          entities
        );

        add_attribute(
          zone_name + "_last_ran",
          config.last_ran_label || "Last Ran",
          "mdi:clock-end",
          [
            { entity: zonestatus, state_not: "on" },
            { entity: zonestatus, state_not: "eco" },
            { entity: zonestatus, state_not: "pending" },
            { entity: showconfig, state: "on" },
          ],
          entities
        );
      } //ZoneHeader

      // Build the Program level entities
      if (config.show_program === true) {
        addProgramRunConfigButtons();
        add_entity([], "start_time", entities);
        add_attribute(
          "remaining",
          config.remaining_label || "Remaining Time",
          "mdi:timer-outline",
          [{ entity: config.program, state: "on" }],
          entities
        );

        //add the program level configuration
        let showconfig = hass.states[config.program].attributes["show_config"];
        add_attr_value("irrigation_on", entities, showconfig);
        add_attr_value("run_freq", entities, showconfig);
        add_attr_value("controller_monitor", entities, showconfig);
        add_attr_value("inter_zone_delay", entities, showconfig);
      }

      //add the zone level configuration
      let first_zone = true;
      for (let i = 1; i < zones + 1; i++) {
        let _zone_name =
          hass.states[config.program].attributes["zone_" + String(i) + "_name"];
        let _zone_type =
          hass.states[config.program].attributes[_zone_name + "_type"];

        if (config.entities) {
          if (config.entities.length > 0) {
            if (config.entities.indexOf(_zone_type + "." + _zone_name) == -1) {
              continue;
            }
          }
        }

        let zone = _zone_type + "." + _zone_name;
        ZoneHeader(zone, _zone_name, first_zone);
        let zone_attrs = [];
        ProcessZone(zone, zone_attrs);
        const newentities = entities.concat(zone_attrs);
        entities = newentities;
        first_zone = false;
      }
      return entities;
    } //cardentities

    if (validconfig === "valid") {
      config.card.entities = cardentities(hass, config.program);
    } else {
      config.card.entities = defentities;
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
      next_run_label: "Next Run",
      last_ran_label: "Last Run",
      remaining_label: "Remaining time",
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
			<div class="row"><label class="label" for="entities">Entity:</label><select class="value" id="entities" multiple></select></div>
			<div class="row"><label class="label" for="show_program">Show program:</label><input type="checkbox" id="show_program" checked></input></div>
			<div class="row"><label class="label" for="last_ran_label">Last ran label:</label><input type="text" id="last_ran_label" defaultValue='Last Ran'></input></div>
			<div class="row"><label class="label" for="next_run_label">Next run label:</label><input type="text" id="next_run_label" defaultValue='Next Run'></input></div>
			<div class="row"><label class="label" for="remaining_label">Remaining label:</label><input type="text" id="remaining_label" defaultValue='Remaining time'></input></div>
			`;
  }
//<div class="row"><label class="label" for="debug">debug:</label><input type="text" id="debug"></input></div>
//this._elements.debug.value = select.value;


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
    this._elements.last_ran_label =
      this._elements.editor.querySelector("#last_ran_label");
    this._elements.next_run_label =
      this._elements.editor.querySelector("#next_run_label");
    this._elements.remaining_label =
      this._elements.editor.querySelector("#remaining_label");

//		this._elements.debug =
//     this._elements.editor.querySelector("#debug");
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
    this._elements.last_ran_label.addEventListener(
      "change",
      this.onChanged.bind(this)
    );
    this._elements.next_run_label.addEventListener(
      "change",
      this.onChanged.bind(this)
    );
    this._elements.remaining_label.addEventListener(
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
		var first = true;
    for (var x in this._hass.states) {
      if (Number(this._hass.states[x].attributes["zone_count"]) > 0) {
        let newOption = new Option(x, x);

        if (x == this._config.program) {
          newOption.selected = true;
        }
        select.add(newOption);
      }
    }

  }

  doBuildEntityOptions(program, entities) {
    // build the list of zones in the program

    var zones = Number(this._hass.states[program].attributes["zone_count"]);
    var select = this._elements.editor.querySelector("#entities");
    //remove existing options
    var i = 0;
    var l = select.options.length - 1;
    for (i = l; i >= 0; i--) {
      select.remove(i);
    }
    //rebuild the options
    for (i = 1; i < zones + 1; i++) {

      let _zone_name =
      hass.states[config.program].attributes["zone_" + String(i) + "_name"];
      let _zone_type =
      hass.states[config.program].attributes["zone_" + String(i) + "_type"];

      var zone_name = _zone_type + "." + _zone_name;
      let newOption = new Option(zone_name, zone_name);
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
    this._elements.last_ran_label.value =
      this._config.last_ran_label || "Last Ran";
    this._elements.next_run_label.value =
      this._config.next_run_label || "Next Run";
    this._elements.remaining_label.value =
      this._config.remaining_label || "Remaining time";
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
    } else if (changedEvent.target.id == "last_ran_label") {
      newConfig.last_ran_label = changedEvent.target.value;
    } else if (changedEvent.target.id == "next_run_label") {
      newConfig.next_run_label = changedEvent.target.value;
    } else if (changedEvent.target.id == "remaining_label") {
      newConfig.remaining_label = changedEvent.target.value;
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