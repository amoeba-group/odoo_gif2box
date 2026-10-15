/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * The banner's words in every language of the website, in a table to edit
 * in place. Typing marks the form as changed; the form's Save writes the
 * cells that were changed, and only those.
 */
export class HeroTranslationsField extends Component {
    static template = "gif2box_hero_banner.HeroTranslationsField";
    static props = { ...standardFieldProps };

    get rows() {
        return this.props.record.data[this.props.name]?.rows || [];
    }

    get columns() {
        return [
            { name: "title", label: _t("Title"), multiline: true },
            { name: "description", label: _t("Description"), multiline: true },
            { name: "button_text", label: _t("Button text"), multiline: false },
        ];
    }

    get stateLabels() {
        return {
            source: _t("Original"),
            machine: _t("Auto-translated"),
            manual: _t("Edited by hand"),
            missing: _t("Not translated"),
        };
    }

    isChanged(row, column) {
        return (row.values[column] || "") !== (row.initial[column] || "");
    }

    rowChanged(row) {
        return this.columns.some((column) => this.isChanged(row, column.name));
    }

    lineCount(row, column) {
        return Math.max(2, (row.values[column] || "").split("\n").length);
    }

    onInput(row, column, ev) {
        const rows = this.rows.map((r) =>
            r.code === row.code ? { ...r, values: { ...r.values, [column]: ev.target.value } } : r
        );
        this.props.record.update({ [this.props.name]: { rows } });
    }
}

registry.category("fields").add("hero_banner_translations", {
    component: HeroTranslationsField,
    supportedTypes: ["json"],
});
