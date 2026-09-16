/**
 * Swallows unhandled promise rejections thrown entirely by browser extensions.
 *
 * Odoo's `error` listener skips third-party scripts, but its
 * `unhandledrejection` listener does not (`@web/core/errors/error_service`):
 * any rejected promise on the page raises the red "UncaughtPromiseError"
 * dialog, including ones from an extension that has wrapped `XMLHttpRequest`
 * and thrown inside its own `onreadystatechange`. A shopper with such an
 * extension sees the dialog on a page that is working perfectly.
 *
 * Odoo already ships one of these guards in the same listener, for the Honey
 * Paypal extension, with the comment "Chrome doesn't seem to sandbox enough
 * the extension [...] We want to ignore those errors as they are not produced
 * by us, and are parasiting the navigation." That guard only matches a
 * `CustomEvent` with no reason, so a real `TypeError` like this one falls
 * through to the dialog.
 *
 * The test is deliberately strict: every frame of the stack has to be an
 * extension URL. One frame of ours anywhere and the error is handled normally,
 * so nothing of our own can be hidden by this.
 */

import { registry } from "@web/core/registry";
import { UncaughtPromiseError } from "@web/core/errors/error_service";

const EXTENSION_SCHEMES = [
    "chrome-extension://",
    "moz-extension://",
    "safari-web-extension://",
    "ms-browser-extension://",
];

function isExtensionOnlyStack(stack) {
    if (typeof stack !== "string") {
        return false;
    }
    // The first line is the message, not a frame.
    const frames = stack
        .split("\n")
        .slice(1)
        .map((line) => line.trim())
        .filter((line) => line);
    if (!frames.length) {
        return false;
    }
    return frames.every((frame) =>
        EXTENSION_SCHEMES.some((scheme) => frame.includes(scheme))
    );
}

function browserExtensionErrorHandler(env, error, originalError) {
    if (!(error instanceof UncaughtPromiseError)) {
        return false;
    }
    if (!originalError || !isExtensionOnlyStack(originalError.stack)) {
        return false;
    }
    if (error.unhandledRejectionEvent) {
        error.unhandledRejectionEvent.preventDefault();
    }
    // Still reported, just not in the shopper's face.
    console.warn("Ignored an error thrown by a browser extension:", originalError);
    return true;
}

// Ahead of every stock handler: the point is to decide before anything can
// turn this into a dialog.
registry
    .category("error_handlers")
    .add("gif2boxBrowserExtensionErrorHandler", browserExtensionErrorHandler, { sequence: 1 });
