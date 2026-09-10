import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = path.resolve(process.cwd(), 'frontend');

/** Execute a classic (non-module) frontend script in the jsdom global scope. */
export function loadScript(relativePath) {
    const code = fs.readFileSync(path.join(FRONTEND, relativePath), 'utf8');
    // eslint-disable-next-line no-new-func
    new Function(code).call(window);
}

/** Same, but expose the HomepageApp class (normally only instantiated on DOMContentLoaded). */
export function loadApp() {
    const code = fs.readFileSync(path.join(FRONTEND, 'js/app.js'), 'utf8');
    // eslint-disable-next-line no-new-func
    new Function(code + '\nwindow.HomepageApp = HomepageApp;').call(window);
}

/** Inject the real index.html body markup (without scripts) into the document. */
export function loadIndexBody() {
    const html = fs.readFileSync(path.join(FRONTEND, 'index.html'), 'utf8');
    const match = html.match(/<body[^>]*>([\s\S]*)<\/body>/i);
    if (!match) throw new Error('index.html body not found');
    document.body.innerHTML = match[1].replace(/<script[\s\S]*?<\/script>/gi, '');
}

export function makeResponse(body, status = 200) {
    return {
        status,
        ok: status >= 200 && status < 300,
        async text() { return body; },
    };
}
