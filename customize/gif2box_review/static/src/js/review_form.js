/**
 * The review form (`views/review_form_templates.xml`).
 *
 * The form posts without this script; with it:
 *  - the stars light up to the one under the finger, and the face and the
 *    words above and below follow;
 *  - photos are shrunk on the phone before they are sent (1600 px, JPEG):
 *    a phone photo is 3 to 6 MB, a few hundred KB once shrunk, which is
 *    what makes sending six of them over 4G bearable;
 *  - the form is sent in the background, with its progress on the
 *    button, and the thank-you replaces it without reloading the page.
 *
 * Loaded on the two review pages only, in a bundle of its own, deferred:
 * not the site's lazily loaded bundle, which arrives after everything
 * else and would leave the first tap on a star without an answer.
 */
(function () {
    "use strict";

    const MAX_SIDE = 1600;
    const QUALITY = 0.85;

    function init(form) {
        form.classList.add("o_g2b_rvf_live");
        const page = form.closest(".o_g2b_rvf");
        const maxImages = parseInt(form.dataset.maxImages, 10) || 6;
        const msg = (key) => {
            const el = form.querySelector(`[data-g2b-msg="${key}"]`);
            return el ? el.textContent.trim() : "";
        };

        // --- Stars ---------------------------------------------------------
        const stars = [...form.querySelectorAll(".o_g2b_rvf_star")];
        const face = form.querySelector(".o_g2b_rvf_face");
        const ratingText = form.querySelector(".o_g2b_rvf_rating_text");
        const ratingBox = form.querySelector(".o_g2b_rvf_rating");
        const ratingError = form.querySelector(".o_g2b_rvf_error_rating");
        const hint = ratingText ? ratingText.textContent : "";

        const current = () => {
            const checked = form.querySelector(".o_g2b_rvf_star_input:checked");
            return checked ? parseInt(checked.value, 10) : 0;
        };
        const paint = (value) => {
            stars.forEach((star, index) => {
                star.classList.toggle("is-on", index < value);
                star.classList.remove("is-hover");
            });
            if (face) {
                if (value) {
                    face.dataset.g2bRating = value;
                } else {
                    delete face.dataset.g2bRating;
                }
            }
            if (ratingText) {
                ratingText.textContent = value ? stars[value - 1].dataset.label : hint;
                ratingText.classList.toggle("o_g2b_rvf_rating_hint", !value);
            }
        };
        stars.forEach((star, index) => {
            const input = star.querySelector("input");
            input.addEventListener("change", () => {
                paint(index + 1);
                stars.forEach((s, i) => s.classList.toggle("is-pop", i === index));
                ratingBox.classList.remove("has-error");
                ratingError.textContent = "";
                if (navigator.vibrate) {
                    navigator.vibrate(8);
                }
            });
            star.addEventListener("pointerenter", (ev) => {
                if (ev.pointerType === "mouse") {
                    stars.forEach((s, i) => s.classList.toggle("is-on", i <= index));
                    if (ratingText) {
                        ratingText.textContent = star.dataset.label;
                    }
                }
            });
        });
        form.querySelector(".o_g2b_rvf_stars").addEventListener("pointerleave", () => {
            stars.forEach((s) => s.classList.remove("is-hover"));
            paint(current());
        });

        // --- Highlights ----------------------------------------------------
        form.querySelectorAll(".o_g2b_rvf_chip input").forEach((input) => {
            input.addEventListener("change", () => {
                input.closest(".o_g2b_rvf_chip").classList.toggle("is-on", input.checked);
            });
        });

        // --- Counter, name -------------------------------------------------
        const comment = form.querySelector("textarea[name=comment]");
        const counter = form.querySelector(".o_g2b_rvf_counter_n");
        const count = () => {
            if (counter && comment) {
                counter.textContent = comment.value.length;
            }
        };
        if (comment) {
            comment.addEventListener("input", count);
            count();
        }
        const name = form.querySelector("input[name=author_name]");
        const mask = form.querySelector(".o_g2b_rvf_mask");
        if (name && mask) {
            name.addEventListener("input", () => {
                const n = name.value.replace(/\s+/g, "");
                mask.textContent = !n ? "" : n.length <= 2 ? n[0] + "*" : n[0] + "***" + n[n.length - 1];
            });
        }
        // Grow the text areas with what is typed.
        form.querySelectorAll(".o_g2b_rvf_textarea").forEach((area) => {
            const grow = () => {
                area.style.height = "auto";
                area.style.height = Math.min(area.scrollHeight + 2, 420) + "px";
            };
            area.addEventListener("input", grow);
        });

        // --- Photos --------------------------------------------------------
        const photosBox = form.querySelector(".o_g2b_rvf_photos");
        const thumbs = form.querySelector(".o_g2b_rvf_thumbs");
        const addItem = form.querySelector(".o_g2b_rvf_add_item");
        const fileInput = form.querySelector(".o_g2b_rvf_file");
        const addCount = form.querySelector(".o_g2b_rvf_add_n");
        const photosError = photosBox.querySelector(".o_g2b_rvf_error");
        const added = []; // {blob, name, li}

        const photoCount = () => thumbs.querySelectorAll(".o_g2b_rvf_thumb").length;
        const refreshPhotos = () => {
            const n = photoCount();
            addCount.textContent = n;
            photosBox.classList.toggle("is-full", n >= maxImages);
        };
        const removeButton = (li, onRemove) => {
            li.querySelector(".o_g2b_rvf_thumb_x").addEventListener("click", () => {
                onRemove();
                li.remove();
                photosError.textContent = "";
                refreshPhotos();
            });
        };
        thumbs.querySelectorAll(".o_g2b_rvf_thumb").forEach((li) => removeButton(li, () => {}));

        const xLabel = msg("remove");

        fileInput.addEventListener("change", async () => {
            const files = [...fileInput.files];
            fileInput.value = "";
            photosError.textContent = "";
            for (const file of files) {
                if (photoCount() >= maxImages) {
                    photosError.textContent = msg("max");
                    break;
                }
                const li = document.createElement("li");
                li.className = "o_g2b_rvf_thumb is-loading";
                li.innerHTML = `<img alt=""/><button type="button" class="o_g2b_rvf_thumb_x">×</button>`;
                li.querySelector("button").setAttribute("aria-label", xLabel || "×");
                thumbs.insertBefore(li, addItem);
                refreshPhotos();
                const entry = { blob: null, name: file.name, li };
                added.push(entry);
                removeButton(li, () => added.splice(added.indexOf(entry), 1));
                const blob = await shrink(file);
                if (!li.isConnected) {
                    continue;
                }
                if (!blob) {
                    added.splice(added.indexOf(entry), 1);
                    li.remove();
                    photosError.textContent = msg("unreadable") + " " + file.name;
                    refreshPhotos();
                    continue;
                }
                entry.blob = blob;
                const img = li.querySelector("img");
                img.src = URL.createObjectURL(blob);
                img.onload = () => li.classList.remove("is-loading");
                img.onerror = () => li.classList.remove("is-loading");
            }
        });
        refreshPhotos();

        // --- Send ----------------------------------------------------------
        const submit = form.querySelector(".o_g2b_rvf_submit");
        const sendError = form.querySelector(".o_g2b_rvf_error_send");
        const success = page.querySelector(".o_g2b_rvf_success");

        form.addEventListener("submit", (ev) => {
            ev.preventDefault();
            sendError.textContent = "";
            if (!current()) {
                ratingBox.classList.remove("has-error");
                void ratingBox.offsetWidth; // restart the shake
                ratingBox.classList.add("has-error");
                ratingError.textContent = msg("rating");
                ratingBox.scrollIntoView({ behavior: "smooth", block: "center" });
                return;
            }
            if (added.some((entry) => !entry.blob)) {
                // Still shrinking: try again in a moment.
                setTimeout(() => form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit")), 300);
                return;
            }
            const data = new FormData(form);
            data.delete("images");
            data.set("ajax", "1");
            added.forEach((entry, index) => {
                data.append("images", entry.blob, (entry.name || "photo").replace(/\.\w+$/, "") + "-" + index + ".jpg");
            });

            submit.disabled = true;
            submit.classList.add("is-busy");
            submit.style.setProperty("--g2b-progress", "4%");

            const xhr = new XMLHttpRequest();
            xhr.open("POST", form.action);
            xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
            xhr.upload.addEventListener("progress", (e) => {
                if (e.lengthComputable) {
                    submit.style.setProperty("--g2b-progress", Math.max(4, Math.round((e.loaded / e.total) * 92)) + "%");
                }
            });
            const fail = (text) => {
                submit.disabled = false;
                submit.classList.remove("is-busy");
                submit.style.setProperty("--g2b-progress", "0%");
                sendError.textContent = text || msg("network");
            };
            xhr.addEventListener("load", () => {
                let result = null;
                try {
                    result = JSON.parse(xhr.responseText);
                } catch {
                    // An HTML page: the session expired, or the server failed.
                }
                if (!result) {
                    fail();
                    return;
                }
                if (!result.ok) {
                    const errors = result.errors || {};
                    if (errors.rating) {
                        ratingError.textContent = errors.rating;
                        ratingBox.classList.add("has-error");
                    }
                    if (errors.images) {
                        photosError.textContent = errors.images;
                    }
                    fail(errors.images || errors.rating || "");
                    return;
                }
                submit.style.setProperty("--g2b-progress", "100%");
                done();
            });
            xhr.addEventListener("error", () => fail());
            xhr.addEventListener("timeout", () => fail());
            xhr.timeout = 120000;
            xhr.send(data);
        });

        function done() {
            const note = form.querySelector("textarea[name=thanks_note]");
            const noteLine = success.querySelector(".o_g2b_rvf_success_note");
            if (noteLine) {
                noteLine.classList.toggle("d-none", !(note && note.value.trim()));
            }
            page.classList.add("is-sent");
            success.classList.add("is-shown");
            window.scrollTo({ top: 0, behavior: "smooth" });
            setTimeout(() => success.focus({ preventScroll: true }), 400);
            if (navigator.vibrate) {
                navigator.vibrate([12, 60, 12]);
            }
        }
    }

    /**
     * The photo, at most MAX_SIDE pixels on its long side, as a JPEG
     * (upright: browsers apply the camera's orientation when decoding).
     * The original when the browser cannot decode it (HEIC on most
     * browsers but Safari): the server then tries, and says so if it
     * cannot either. null for what is not an image at all.
     */
    async function shrink(file) {
        if (file.type && !file.type.startsWith("image/")) {
            return null;
        }
        try {
            const source = await decode(file);
            const scale = Math.min(1, MAX_SIDE / Math.max(source.width, source.height));
            const width = Math.round(source.width * scale);
            const height = Math.round(source.height * scale);
            const canvas = document.createElement("canvas");
            canvas.width = width;
            canvas.height = height;
            const ctx = canvas.getContext("2d");
            ctx.fillStyle = "#fff";
            ctx.fillRect(0, 0, width, height);
            ctx.drawImage(source, 0, 0, width, height);
            if (source.close) {
                source.close();
            }
            const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", QUALITY));
            return blob || file;
        } catch {
            return file;
        }
    }

    function decode(file) {
        if (window.createImageBitmap) {
            return createImageBitmap(file, { imageOrientation: "from-image" }).catch(() => decodeWithImg(file));
        }
        return decodeWithImg(file);
    }

    function decodeWithImg(file) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = reject;
            img.src = URL.createObjectURL(file);
        });
    }

    /**
     * Lift the site's page loader (`gif2box_theme_home`) as soon as the
     * form can be used: it otherwise waits for the lazily loaded bundle,
     * seconds on a phone that has just scanned the card, during which a
     * tap on a star lands on the loader.
     */
    function liftLoader() {
        const loader = document.getElementById("gif2box_loader");
        if (!loader || loader.classList.contains("o_gif2box_loader_done")) {
            return;
        }
        loader.classList.add("o_gif2box_loader_done");
        setTimeout(() => loader.remove(), 400);
    }

    function start() {
        document.querySelectorAll(".o_g2b_rvf_form").forEach(init);
        liftLoader();
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
