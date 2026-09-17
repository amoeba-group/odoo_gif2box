/**
 * Clears Bootstrap's leftover swipe timeout when a carousel is disposed.
 *
 * On touch end, `Carousel._addTouchEventListeners` schedules a callback to
 * resume auto-play once the swipe has settled:
 *
 *     this.touchTimeout = setTimeout(
 *         () => this._maybeEnableCycle(),
 *         TOUCHEVENT_COMPAT_WAIT + this._config.interval);
 *
 * With `data-carousel-interval="5000"` on the product snippets, that fires
 * about five and a half seconds after the finger leaves the screen.
 * `Carousel.dispose()` disposes the swipe helper and hands off to
 * `BaseComponent.dispose()`, which nulls every property -- but nothing clears
 * `touchTimeout`. `_clearInterval()` covers the auto-play interval and only
 * that. So an orphaned timeout survives the instance, fires, and
 * `_maybeEnableCycle` reads `this._config.ride` off null:
 *
 *     TypeError: Cannot read properties of null (reading 'ride')
 *
 * A carousel is disposed here whenever a dynamic snippet re-renders -- the
 * window crossing the `sm` breakpoint, a phone rotating, or an add-to-cart on
 * a snippet marked `add2cart_rerender`. Swipe a product carousel, have any of
 * those happen within the next five seconds, and the shopper gets the red
 * error dialog on a page that is otherwise fine.
 *
 * Bootstrap is exposed as globals in this bundle (`window.Carousel`), the same
 * way `website` reaches `Dropdown` and `Offcanvas`.
 */

const Carousel = window.Carousel;

if (Carousel && Carousel.prototype && !Carousel.prototype._g2bDisposePatched) {
    const dispose = Carousel.prototype.dispose;

    Carousel.prototype.dispose = function () {
        if (this.touchTimeout) {
            clearTimeout(this.touchTimeout);
            this.touchTimeout = null;
        }
        return dispose.apply(this, arguments);
    };

    Carousel.prototype._g2bDisposePatched = true;
}
