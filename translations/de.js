{
	"config": {
		"step": {
			"user": {
				"title": "Programmdaten",
				"description": "Daten eingeben, um das Programm zu definieren",
				"data": {
					"name": "Name",
					"friendly_name": "Anzeige Name",
					"run_freq": "Entity für Ausführungs-Häufigkeit",
					"controller_monitor": "Monitor controller entity",
					"start_time": "Startzeit entity",
					"irrigation_on": "Entity um Programm zu aktivieren",
					"show_config": "Entity um Einstellungen anzuzeigen",
					"inter_zone_delay": "Entity für Verzögerung zwischen zwei Zonen"
				}
			},
			"zones": {
				"title": "Programm Zonen",
				"description": "Zonen Einstellungen",
				"data": {
					"zone": "Zonenschalter",
					"friendly_name": "Anzeige Name",
					"pump": "Pumpen-Schalter",
					"flow_sensor": "Durchfluss-Sensor",
					"water_adjustment": "Entity für Laufzeit-Anpassung",
					"run_freq": "Entity für Laufzeit-Häufigkeit",
					"rain_sensor": "Regensensor",
					"zone_group": "Zonengruppe",
					"water": "Entity für Laufzeit",
					"wait": "Entity für Wartezeit zwischen Wiederholungen",
					"repeat": "Entity für Wiederholungs-Anzahl",
					"ignore_rain_sensor": "Entity zum Ignorieren des Regensensors",
					"enable_zone": "Zonenschalter",
					"add_another": "weitere Zone hinzufügen"
				}
			}
		},
    "create_entry": {
      "default": ""
    },
		"error": {
				"import_error": "Fehler beim importieren der YAML"
		}
	},

  "options": {
    "step": {
			"user": {
				"menu_options": {
					"update_program": "Programm Optionen aktualisieren",
					"update_zone": "Zonen Optionen aktualisieren",
					"delete_zone": "Zone löschen",
					"add_zone": "Zone hinzufügen",
					"apply_changes": "Änderungen ausführen"
				}
			},
			"update_program": {
				"title": "Programm Daten",
				"description": "Programmdaten aktualisierten",
				"data": {
						"name": "Name",
						"friendly_name": "Friendly name",
					    "run_freq": "Entity für Ausführungs-Häufigkeit",
					    "controller_monitor": "Monitor controller entity",
					    "start_time": "Startzeit entity",
					    "irrigation_on": "Entity um Bewässerung zu aktivieren",
					    "show_config": "Entity um Einstellungen anzuzeigen",
					    "inter_zone_delay": "Entity für Verzögerung zwischen zwei Zonen"
				}
			},
			"add_zone": {
				"title": "Programm Zonen",
				"description": "Zonen Einstellungen",
				"data": {
					"zone": "Zonenschalter",
					"friendly_name": "Anzeige Name",
					"pump": "Pumpenschalter",
					"flow_sensor": "Durchfluss Sensor",
					"water_adjustment": "Entity für Laufzeitanpassungen",
					"run_freq": "Entity für Ausführungs-Häufigkeit",
					"rain_sensor": "Regen Sensor",
					"zone_group": "Zonengruppe",
					"water": "Entity für Laufzeit",
					"wait": "Entity für Wartezeit zwischen Wiederholungen",
					"repeat": "Entity für Wiederholungsanzahl",
					"ignore_rain_sensor": "Entity um Regensensor zu ignorieren",
					"enable_zone": "Entity um Zone zu aktivieren",
					"add_another": "Weitere Zone hinzufügen"
				}
			},
			"update_zone_data": {
				"title": "Programm Zonen",
				"description": "Zonen Einstellungen",
				"data": {
					"zone": "Zonenschalter",
					"friendly_name": "Anzeige Name",
					"pump": "Pumpen-Schalter",
					"flow_sensor": "Durchfluss-Sensor",
					"water_adjustment": "Entity für Laufzeit-Anpassung",
					"run_freq": "Entity für Ausführungs-Häufigkeit",
					"rain_sensor": "Regensensor",
					"zone_group": "Zonengruppe",
					"water": "Entity für Laufzeit",
 					"wait": "Entity für Verzögerung zwischen zwei Zonen",
					"repeat": "Entity für Wiederholungs-Anzahl",
					"ignore_rain_sensor": "Entity zum Ignorieren des Regensensors",
					"enable_zone": "Zonenschalter",
				}
			},
			"delete_zone": {
				"title": "Zone löschen",
				"description": "Zonen Einstellungen",
				"data": {
					"zone": "Zone auswählen"
				}
			},
			"update_zone": {
				"title": "Zone aktualisieren",
				"description": "Zonen Einstellungen",
				"data": {
					"zone": "Zone auswählen"
				}
			}
		}
	}
}
