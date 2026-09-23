const ts = () => new Date().toISOString();

export const log = (...args) => console.log(ts(), '[backend]', ...args);
export const logErr = (...args) => console.error(ts(), '[backend]', ...args);
