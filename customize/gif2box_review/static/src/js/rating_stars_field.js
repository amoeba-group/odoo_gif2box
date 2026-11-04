/** @odoo-module **/
/**
 * Stars for a 1-to-5 integer: five of them, the ones up to the rating
 * filled. Click a star to set the rating; read-only in lists and kanban.
 * Odoo's "priority" widget needs a selection and keeps its first value for
 * "no star", which a review cannot have.
 */
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class RatingStarsField extends Component {
    static template = "gif2box_review.RatingStarsField";
    static props = { ...standardFieldProps };

    get value() {
        return this.props.record.data[this.props.name] || 0;
    }

    get stars() {
        return [1, 2, 3, 4, 5];
    }

    get label() {
        return _t("%s out of 5 stars", this.value);
    }

    onClick(stars) {
        if (!this.props.readonly) {
            this.props.record.update({ [this.props.name]: stars });
        }
    }
}

registry.category("fields").add("g2b_rating_stars", {
    component: RatingStarsField,
    supportedTypes: ["integer"],
});
