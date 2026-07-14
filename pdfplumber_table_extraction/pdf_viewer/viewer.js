import * as pdfjsLib from
    "https://cdn.jsdelivr.net/npm/pdfjs-dist@5.4.149/build/pdf.min.mjs";

pdfjsLib.GlobalWorkerOptions.workerSrc =
    "https://cdn.jsdelivr.net/npm/pdfjs-dist@5.4.149/build/pdf.worker.min.mjs";

export default async function(component) {
    const {
        data,
        parentElement,
        setStateValue,
    } = component;

    const canvas = parentElement.querySelector("#pdf-canvas");
    const canvasContext = canvas.getContext("2d");
    const currentPageElement = parentElement.querySelector("#current-page");
    const pageCountElement = parentElement.querySelector("#page-count");
    const previousPageButton = parentElement.querySelector("#previous-page");
    const nextPageButton = parentElement.querySelector("#next-page");

    const binaryPdfData = Uint8Array.from(
        atob(data.pdf_base64),
        character => character.charCodeAt(0),
    );

    const pdfDocument = await pdfjsLib.getDocument({
        data: binaryPdfData,
    }).promise;

    let currentPageNumber = data.initial_page ?? 1;
    let renderingInProgress = false;
    let pendingPageNumber = null;

    pageCountElement.textContent = String(pdfDocument.numPages);

    async function renderPage(pageNumber) {
        renderingInProgress = true;

        const pdfPage = await pdfDocument.getPage(pageNumber);
        const viewport = pdfPage.getViewport({
            scale: data.scale ?? 1.5,
        });

        canvas.width = viewport.width;
        canvas.height = viewport.height;

        await pdfPage.render({
            canvasContext,
            viewport,
        }).promise;

        renderingInProgress = false;
        currentPageElement.textContent = String(pageNumber);

        previousPageButton.disabled = pageNumber <= 1;
        nextPageButton.disabled = pageNumber >= pdfDocument.numPages;

        setStateValue("page_number", pageNumber);
        setStateValue("page_count", pdfDocument.numPages);

        if (pendingPageNumber !== null) {
            const requestedPageNumber = pendingPageNumber;
            pendingPageNumber = null;
            await renderPage(requestedPageNumber);
        }
    }

    function requestPage(pageNumber) {
        currentPageNumber = Math.max(
            1,
            Math.min(pageNumber, pdfDocument.numPages),
        );

        if (renderingInProgress) {
            pendingPageNumber = currentPageNumber;
            return;
        }

        void renderPage(currentPageNumber);
    }

    previousPageButton.onclick = () => {
        requestPage(currentPageNumber - 1);
    };

    nextPageButton.onclick = () => {
        requestPage(currentPageNumber + 1);
    };

    await renderPage(currentPageNumber);
}
