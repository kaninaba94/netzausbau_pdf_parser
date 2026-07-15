import * as pdfjsLib from "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.min.mjs";

pdfjsLib.GlobalWorkerOptions.workerSrc =
    "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.worker.min.mjs";


export default async function pdfPointsPicker(component) {
    const container = component.parentElement.querySelector("#pdf-page");

    const pdfBytes = Uint8Array.from(
        atob(component.data.pdf_base64),
        character => character.charCodeAt(0),
    );

    const pdf = await pdfjsLib.getDocument(pdfBytes).promise;
    const page = await pdf.getPage(1);
    const viewport = page.getViewport({ scale: 1.5 });

    const canvas = document.createElement("canvas");
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    container.appendChild(canvas);

    await page.render({
        canvasContext: canvas.getContext("2d"),
        viewport,
    }).promise;
    
    let points = [];
    canvas.onclick = event => {
        const bounds = canvas.getBoundingClientRect();

        const point = {
            x: event.offsetX / bounds.width,
            y: event.offsetY / bounds.height,
        };
        points.push(point)

        component.setStateValue("points", points);
    };
    canvas.oncontextmenu = event => {
        event.preventDefault();
        points.pop();
        component.setStateValue("points", points)
    }
}
