import * as vscode from 'vscode';
import MarkdownIt from 'markdown-it';
import * as os from 'os';

const SESSION_CONFIG_LANG = "session-config";
const MSG_METADATA_LANG = "msg-metadata";
const LAST_SAVE_DIR_KEY = 'Domarkx.lastSaveDirectory';

interface ParsedCodeBlockLocation {
	uri: vscode.Uri;
	startLine: number;
	language?: string;
}

interface CommandConfigBase {
	title: string;
	command: string;
}

interface CodeBlockCommandConfig extends CommandConfigBase { }
interface MessageBlockCommandConfig extends CommandConfigBase { }

interface ExecuteCodeBlockCommandArgs {
	uri: vscode.Uri;
	startLine: number;
	language?: string;
	messageIndex: number;
	codeBlockInMessageIndex: number;
	commandTemplate: string;
}

interface ExecuteMessageBlockCommandArgs {
	uri: vscode.Uri;
	messageIndex: number;
	commandTemplate: string;
	speakerName: string;
	speakerText: string;
	messageContentStartLine?: number;
	messageContentEndLine?: number;
}

interface MessageBlock {
	speakerLine: number;
	speakerText: string;
	speakerName: string;
	startLine: number;
	endLine: number;
	messageContentStartLine?: number;
	messageContentEndLine?: number;
	codeBlocksInMessage: ParsedCodeBlockLocation[];
}

let _documentExecutionTerminal: vscode.Terminal | undefined;
let _codeBlockExecutionTerminal: vscode.Terminal | undefined;
let _messageBlockExecutionTerminal: vscode.Terminal | undefined;

const md = new MarkdownIt();
let _context: vscode.ExtensionContext | undefined;
let lastUsedSaveDirectoryUri: vscode.Uri | undefined;

export function activate(context: vscode.ExtensionContext) {
	console.log('Domarkx Tools extension is now active.');
	_context = context;
	const lastDirString = _context.globalState.get<string>(LAST_SAVE_DIR_KEY);
	if (lastDirString) {
		try {
			lastUsedSaveDirectoryUri = vscode.Uri.parse(lastDirString);
		} catch (e) {
			console.error("Domarkx Tools: Failed to parse last saved directory URI from global state:", e);
			lastUsedSaveDirectoryUri = undefined;
		}
	}

	const codeLensProvider = new DomarkxDocCodeLensProvider();
	context.subscriptions.push(
		vscode.languages.registerCodeLensProvider({ language: 'markdown' }, codeLensProvider)
	);

	context.subscriptions.push(
		vscode.commands.registerCommand('Domarkx.extractBefore', async (documentUri: vscode.Uri, messageBlockIndex: number) => {
			await extractAndOpen(documentUri, messageBlockIndex, false);
		})
	);

	context.subscriptions.push(
		vscode.commands.registerCommand('Domarkx.extractIncludingCurrent', async (documentUri: vscode.Uri, messageBlockIndex: number) => {
			await extractAndOpen(documentUri, messageBlockIndex, true);
		})
	);

	context.subscriptions.push(
		vscode.commands.registerCommand('Domarkx.executeCustomCommand', async (uri?: vscode.Uri) => {
			let documentUriForExecution = uri;
			if (!documentUriForExecution && vscode.window.activeTextEditor) {
				documentUriForExecution = vscode.window.activeTextEditor.document.uri;
			}

			if (documentUriForExecution) {
				await executeDocumentCommand(documentUriForExecution);
			} else {
				vscode.window.showErrorMessage("No active document found to execute.");
			}
		})
	);

	context.subscriptions.push(
		vscode.commands.registerCommand('Domarkx.executeCodeBlockCommand',
			async (args: ExecuteCodeBlockCommandArgs) => {
				await executeCodeBlockInTerminal(args);
			}
		)
	);

	context.subscriptions.push(
		vscode.commands.registerCommand('Domarkx.executeMessageBlockCommand',
			async (args: ExecuteMessageBlockCommandArgs) => {
				await executeMessageBlockInTerminal(args);
			}
		)
	);

	context.subscriptions.push({
		dispose: () => {
			if (_documentExecutionTerminal) {
				_documentExecutionTerminal.dispose();
			}
			if (_codeBlockExecutionTerminal) {
				_codeBlockExecutionTerminal.dispose();
			}
			if (_messageBlockExecutionTerminal) {
				_messageBlockExecutionTerminal.dispose();
			}
		}
	});
}

class DomarkxDocCodeLensProvider implements vscode.CodeLensProvider {
	private _onDidChangeCodeLenses: vscode.EventEmitter<void> = new vscode.EventEmitter<void>();
	public readonly onDidChangeCodeLenses: vscode.Event<void> = this._onDidChangeCodeLenses.event;

	constructor() {
		vscode.workspace.onDidChangeTextDocument(e => {
			if (e.document.languageId === 'markdown') {
				this._onDidChangeCodeLenses.fire();
			}
		});

		vscode.workspace.onDidChangeConfiguration(e => {
			if (
				e.affectsConfiguration('Domarkx.executionCommand') ||
				e.affectsConfiguration('Domarkx.executionCodelensTitle') ||
				e.affectsConfiguration('Domarkx.showExecuteActionAsCodelens') ||
				e.affectsConfiguration('Domarkx.codeBlockCommands') ||
				e.affectsConfiguration('Domarkx.messageBlockCommands')
			) {
				this._onDidChangeCodeLenses.fire();
			}
		});
	}

	public provideCodeLenses(document: vscode.TextDocument, cancellationToken: vscode.CancellationToken): vscode.ProviderResult<vscode.CodeLens[]> {
		if (cancellationToken.isCancellationRequested) {
			return [];
		}
		const lenses: vscode.CodeLens[] = [];
		const config = vscode.workspace.getConfiguration('Domarkx');
		const text = document.getText();
		let tokens: MarkdownIt.Token[];
		try {
			tokens = md.parse(text, {});
		} catch (e) {
			console.error("Markdown parsing error:", e);
			vscode.window.showErrorMessage("Error parsing Markdown document. Some features might not work correctly.");
			return [];
		}

		const executionCommand = config.get<string>('executionCommand');
		const executionLensTitle = config.get<string>('executionCodelensTitle', '▶️ Execute Document');
		const showExecuteAsCodelens = config.get<boolean>('showExecuteActionAsCodelens');

		if (showExecuteAsCodelens && executionCommand && executionCommand.trim() !== "") {
			let configBlockLineNum = 0;
			for (const t of tokens) {
				if (t.type === 'fence' && t.info.trim().toLowerCase() === SESSION_CONFIG_LANG && t.map) {
					configBlockLineNum = t.map[0];
					break;
				}
			}

			if (configBlockLineNum >= document.lineCount) configBlockLineNum = document.lineCount > 0 ? document.lineCount - 1 : 0;

			const range = document.lineAt(configBlockLineNum).range;
			const tooltipFileName = document.isUntitled ? "untitle.md" : document.fileName;
			lenses.push(new vscode.CodeLens(range, {
				title: executionLensTitle,
				command: "Domarkx.executeCustomCommand",
				arguments: [document.uri],
				tooltip: `Run: ${executionCommand.replace('${file}', `"${tooltipFileName}"`)}`
			}));
		}

		const messageBlocks = parseMessageBlocksFromTokens(document.uri, tokens, text);

		const messageBlockCommands = config.get<MessageBlockCommandConfig[]>('messageBlockCommands');
		messageBlocks.forEach((block, messageIndex) => {
			const validSpeakerLine = Math.min(Math.max(0, block.speakerLine), document.lineCount - 1);
			const lineText = document.lineAt(validSpeakerLine).text;
			const range = new vscode.Range(validSpeakerLine, 0, validSpeakerLine, lineText.length);

			lenses.push(new vscode.CodeLens(range, {
				title: "New Doc (Before)",
				command: "Domarkx.extractBefore",
				arguments: [document.uri, messageIndex]
			}));
			lenses.push(new vscode.CodeLens(range, {
				title: "New Doc (Including)",
				command: "Domarkx.extractIncludingCurrent",
				arguments: [document.uri, messageIndex]
			}));

			if (messageBlockCommands && Array.isArray(messageBlockCommands) && messageBlockCommands.length > 0) {
				messageBlockCommands.forEach(cmdConfig => {
					if (!cmdConfig.title || !cmdConfig.command) {
						return;
					}

					const commandArgs: ExecuteMessageBlockCommandArgs = {
						uri: document.uri,
						messageIndex: messageIndex,
						commandTemplate: cmdConfig.command,
						speakerName: block.speakerName,
						speakerText: block.speakerText,
						messageContentStartLine: block.messageContentStartLine,
						messageContentEndLine: block.messageContentEndLine,
					};
					const tooltip = `Run: ${cmdConfig.command
						.replace(/\$\{file\}/g, `"${document.uri.fsPath}"`)
						.replace(/\$\{messageIndex\}/g, messageIndex.toString())
						.replace(/\$\{messageSpeaker\}/g, block.speakerName)
						.replace(/\$\{messageSpeakerText\}/g, JSON.stringify(block.speakerText))
						.replace(/\$\{messageStartLine\}/g, block.startLine.toString())
						.replace(/\$\{messageEndLine\}/g, block.endLine.toString())
						.replace(/\$\{messageContentStartLine\}/g, block.messageContentStartLine?.toString() || '')
						.replace(/\$\{messageContentEndLine\}/g, block.messageContentEndLine?.toString() || '')
						.replace(/\$\{messageContent\}/g, '<message content not shown in tooltip>')
						.replace(/\$\{messageContentBase64\}/g, '<message content not shown in tooltip>')
						}`;

					lenses.push(new vscode.CodeLens(range, {
						title: cmdConfig.title,
						command: "Domarkx.executeMessageBlockCommand",
						arguments: [commandArgs],
						tooltip: tooltip
					}));
				});
			}

			const codeBlockCommands = config.get<CodeBlockCommandConfig[]>('codeBlockCommands');
			if (codeBlockCommands && Array.isArray(codeBlockCommands) && codeBlockCommands.length > 0) {
				block.codeBlocksInMessage.forEach((parsedCbLocation, codeBlockInMessageIndex) => {
					const zeroIndexedStartLine = parsedCbLocation.startLine - 1;
					if (zeroIndexedStartLine < 0 || zeroIndexedStartLine >= document.lineCount) {
						console.warn(`Code block startLine ${parsedCbLocation.startLine} out of bounds for document ${document.uri.fsPath}`);
						return;
					}

					const codeBlockRange = document.lineAt(zeroIndexedStartLine).range;
					codeBlockCommands.forEach(cmdConfig => {
						if (!cmdConfig.title || !cmdConfig.command) {
							return;
						}

						const commandArgs: ExecuteCodeBlockCommandArgs = {
							uri: parsedCbLocation.uri,
							startLine: parsedCbLocation.startLine,
							language: parsedCbLocation.language,
							messageIndex: messageIndex,
							codeBlockInMessageIndex: codeBlockInMessageIndex,
							commandTemplate: cmdConfig.command
						};
						const tooltip = `Run: ${cmdConfig.command
							.replace(/\$\{file\}/g, `"${document.uri.fsPath}"`)
							.replace(/\$\{lineNumber\}/g, parsedCbLocation.startLine.toString())
							.replace(/\$\{language\}/g, parsedCbLocation.language || '')
							.replace(/\$\{messageIndex\}/g, messageIndex.toString())
							.replace(/\$\{codeBlockInMessageIndex\}/g, codeBlockInMessageIndex.toString())
							}`;

						lenses.push(new vscode.CodeLens(codeBlockRange, {
							title: cmdConfig.title,
							command: "Domarkx.executeCodeBlockCommand",
							arguments: [commandArgs],
							tooltip: tooltip
						}));
					});
				});
			}
		});
		return lenses;
	}
}

function parseMessageBlocksFromTokens(docUri: vscode.Uri, tokens: MarkdownIt.Token[], fullText: string): MessageBlock[] {
	const messageBlocks: MessageBlock[] = [];
	let currentMessageBlock: Partial<MessageBlock> & { codeBlocksInMessage?: ParsedCodeBlockLocation[] } | null = null;
	let inMessageBlockquoteDepth = 0;
	const lines = fullText.split(/\r\n|\r|\n/);

	for (let i = 0; i < tokens.length; i++) {
		const token = tokens[i];
		if (!token.map) continue;

		if (token.level === 0 && token.type === 'heading_open' && token.tag === 'h2' && token.markup === '##') {
			if (currentMessageBlock?.startLine !== undefined) {
				currentMessageBlock.endLine = token.map[0];
				if (currentMessageBlock.messageContentStartLine !== undefined && currentMessageBlock.messageContentEndLine === undefined) {
					currentMessageBlock.messageContentEndLine = token.map[0];
				}
				if (currentMessageBlock.messageContentStartLine !== undefined &&
					currentMessageBlock.messageContentEndLine !== undefined &&
					currentMessageBlock.messageContentEndLine <= currentMessageBlock.messageContentStartLine) {
					currentMessageBlock.messageContentStartLine = undefined;
					currentMessageBlock.messageContentEndLine = undefined;
				}
				messageBlocks.push(currentMessageBlock as MessageBlock);
			}

			const speakerLine = token.map[0];
			const nextToken = tokens[i + 1];
			const speakerName = nextToken?.content?.trim() || 'Unknown Speaker';
			const speakerTextLineContent = lines[speakerLine];
			const speakerTextMatch = speakerTextLineContent.match(/^(##\s*.+)/);
			const speakerText = speakerTextMatch ? speakerTextMatch[1] : `## ${speakerName}`;

			currentMessageBlock = {
				speakerLine: speakerLine,
				speakerText: speakerText,
				speakerName: speakerName,
				startLine: speakerLine,
				codeBlocksInMessage: [],
			};
			inMessageBlockquoteDepth = 0;

			if (tokens[i + 1]?.type === 'inline' && tokens[i + 2]?.type === 'heading_close') {
				i += 2;
			} else if (tokens[i + 1]?.type === 'inline') {
				i += 1;
			}
			continue;
		}

		if (currentMessageBlock) {
			if (token.type === 'fence' && token.info.trim().toLowerCase() === MSG_METADATA_LANG) {
				if (currentMessageBlock.messageContentStartLine === undefined) {
					currentMessageBlock.messageContentStartLine = token.map[1];
				}
				continue;
			}

			if (token.type === 'blockquote_open') {
				inMessageBlockquoteDepth++;
				if (inMessageBlockquoteDepth === 1 && currentMessageBlock.messageContentStartLine === undefined) {
					currentMessageBlock.messageContentStartLine = token.map[0];
				}
			}

			if (token.type === 'blockquote_close') {
				inMessageBlockquoteDepth = Math.max(0, inMessageBlockquoteDepth - 1);
				if (inMessageBlockquoteDepth === 0 && currentMessageBlock.messageContentStartLine !== undefined && currentMessageBlock.messageContentEndLine === undefined) {
					currentMessageBlock.messageContentEndLine = token.map[0];
				}
			}

			if (token.type === 'fence' && inMessageBlockquoteDepth > 0) {
				currentMessageBlock.codeBlocksInMessage!.push({
					uri: docUri,
					startLine: token.map[0] + 1,
					language: token.info.trim() || undefined,
				});
				if (currentMessageBlock.messageContentStartLine !== undefined) {
					currentMessageBlock.messageContentEndLine = token.map[1];
				}
			}
			else if (token.type === 'paragraph_open') {
				if (inMessageBlockquoteDepth > 0) {
					if (currentMessageBlock.messageContentStartLine === undefined) {
						currentMessageBlock.messageContentStartLine = token.map[0];
					}
					currentMessageBlock.messageContentEndLine = token.map[1];
				} else if (currentMessageBlock.messageContentStartLine === undefined &&
					currentMessageBlock.startLine !== undefined &&
					token.map[0] > currentMessageBlock.startLine &&
					currentMessageBlock.codeBlocksInMessage?.length === 0 &&
					!Object.prototype.hasOwnProperty.call(currentMessageBlock, 'messageContentEndLine')
				) {
					if (lines[token.map[0]] && lines[token.map[0]].trim().length > 0) {
						currentMessageBlock.messageContentStartLine = token.map[0];
						currentMessageBlock.messageContentEndLine = token.map[1];
					}
				}
			}
		}
	}

	if (currentMessageBlock?.startLine !== undefined) {
		currentMessageBlock.endLine = lines.length;
		if (currentMessageBlock.messageContentStartLine !== undefined && currentMessageBlock.messageContentEndLine === undefined) {
			currentMessageBlock.messageContentEndLine = lines.length;
		}
		if (currentMessageBlock.messageContentStartLine !== undefined &&
			currentMessageBlock.messageContentEndLine !== undefined &&
			currentMessageBlock.messageContentEndLine <= currentMessageBlock.messageContentStartLine) {
			currentMessageBlock.messageContentStartLine = undefined;
			currentMessageBlock.messageContentEndLine = undefined;
		}
		messageBlocks.push(currentMessageBlock as MessageBlock);
	}
	return messageBlocks;
}

async function extractAndOpen(documentUri: vscode.Uri, messageBlockIndex: number, includeCurrent: boolean) {
	const document = await vscode.workspace.openTextDocument(documentUri);
	const fullText = document.getText();
	const lines = fullText.split(/\r\n|\r|\n/);
	let newContent = "";
	const tokens = md.parse(fullText, {});
	const allMessageBlocks = parseMessageBlocksFromTokens(document.uri, tokens, fullText);

	if (messageBlockIndex < 0 || messageBlockIndex >= allMessageBlocks.length) {
		vscode.window.showErrorMessage("Invalid message block index for extraction.");
		return;
	}

	let endExtractionLineExclusive: number;

	if (!includeCurrent) {
		const currentBlock = allMessageBlocks[messageBlockIndex];
		endExtractionLineExclusive = currentBlock.speakerLine;
	} else {
		const nextBlockIndex = messageBlockIndex + 1;
		if (nextBlockIndex < allMessageBlocks.length) {
			const nextBlock = allMessageBlocks[nextBlockIndex];
			endExtractionLineExclusive = nextBlock.speakerLine;
		} else {
			endExtractionLineExclusive = lines.length;
		}
	}

	endExtractionLineExclusive = Math.max(0, Math.min(endExtractionLineExclusive, lines.length));

	for (let i = 0; i < endExtractionLineExclusive; i++) {
		newContent += lines[i] + (i === endExtractionLineExclusive - 1 && i === lines.length - 1 ? "" : "\n");
	}

	if (newContent.length > 0) {
		newContent = newContent.trimEnd() + '\n';
	} else {
		newContent = '\n';
	}

	const newDoc = await vscode.workspace.openTextDocument({ content: newContent, language: 'markdown' });
	await vscode.window.showTextDocument(newDoc);
}

function ensureTerminal(name: string, currentTerminalRef: vscode.Terminal | undefined): vscode.Terminal {
	if (!currentTerminalRef || currentTerminalRef.exitStatus !== undefined) {
		if (currentTerminalRef) currentTerminalRef.dispose();
		currentTerminalRef = vscode.window.createTerminal(name);
	}
	return currentTerminalRef;
}

async function saveDocumentBeforeExecution(documentUri: vscode.Uri): Promise<vscode.Uri | undefined> {
	let document = await vscode.workspace.openTextDocument(documentUri);

	if (document.isUntitled) {
		const saveChoice = await vscode.window.showWarningMessage(
			"This is an untitled document and must be saved before execution.",
			{ modal: true },
			"Save",
			"Cancel"
		);

		if (saveChoice === "Save") {
			const now = new Date();
			const defaultFilename = `${now.getFullYear()}${(now.getMonth() + 1).toString().padStart(2, '0')}${now.getDate().toString().padStart(2, '0')}_${now.getHours().toString().padStart(2, '0')}${now.getMinutes().toString().padStart(2, '0')}.md`;

			let defaultDialogDirUri: vscode.Uri | undefined = lastUsedSaveDirectoryUri;
			if (!defaultDialogDirUri) {
				if (vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders.length > 0) {
					defaultDialogDirUri = vscode.workspace.workspaceFolders[0].uri;
				} else {
					try {
						const homeDir = os.homedir();
						if (homeDir) {
							defaultDialogDirUri = vscode.Uri.file(homeDir);
						}
					} catch (e) { console.warn("Domarkx Tools: Could not determine home directory for default save.", e); }
				}
			}

			const suggestedSaveUri = defaultDialogDirUri
				? vscode.Uri.joinPath(defaultDialogDirUri, defaultFilename)
				: vscode.Uri.file(defaultFilename);

			const userChosenUri = await vscode.window.showSaveDialog({
				defaultUri: suggestedSaveUri,
				saveLabel: "Save and Execute",
				filters: { 'Markdown': ['md'] }
			});

			if (userChosenUri) {
				try {
					const originalUntitledUri = document.uri;
					const content = Buffer.from(document.getText(), 'utf8');
					await vscode.workspace.fs.writeFile(userChosenUri, content);

					await vscode.window.showTextDocument(originalUntitledUri);
					await vscode.commands.executeCommand('workbench.action.revertAndCloseActiveEditor');

					const newDoc = await vscode.workspace.openTextDocument(userChosenUri);
					await vscode.window.showTextDocument(newDoc, { preview: false });

					const parentDirUri = vscode.Uri.joinPath(userChosenUri, '..');
					lastUsedSaveDirectoryUri = parentDirUri;
					if (_context) {
						await _context.globalState.update(LAST_SAVE_DIR_KEY, parentDirUri.toString());
					}

					vscode.window.showInformationMessage(`Document saved to ${userChosenUri.fsPath}. Continuing execution.`);
					return userChosenUri;
				} catch (error: any) {
					vscode.window.showErrorMessage(`Error saving or closing the file: ${error.message || error}`);
					return undefined;
				}
			} else {
				vscode.window.showInformationMessage("Save operation was cancelled. Execution aborted.");
				return undefined;
			}
		} else {
			vscode.window.showInformationMessage("Execution cancelled because the document was not saved.");
			return undefined;
		}
	} else if (document.isDirty) {
		const saveChoice = await vscode.window.showWarningMessage(
			"The document has unsaved changes. Save before executing?",
			{ modal: true },
			"Save",
			"Execute Anyway",
			"Cancel"
		);

		if (saveChoice === "Save") {
			if (!(await document.save())) {
				vscode.window.showErrorMessage("Failed to save the document. Execution cancelled.");
				return undefined;
			}
			vscode.window.showInformationMessage("Document saved.");
		} else if (saveChoice === "Cancel") {
			vscode.window.showInformationMessage("Execution cancelled.");
			return undefined;
		}
	}

	return documentUri;
}

async function executeCommandInSpecificTerminal(command: string, terminalName: string, terminalType: 'document' | 'codeBlock' | 'messageBlock') {
	let targetTerminal: vscode.Terminal;
	switch (terminalType) {
		case 'document':
			_documentExecutionTerminal = ensureTerminal(terminalName, _documentExecutionTerminal);
			targetTerminal = _documentExecutionTerminal;
			break;
		case 'codeBlock':
			_codeBlockExecutionTerminal = ensureTerminal(terminalName, _codeBlockExecutionTerminal);
			targetTerminal = _codeBlockExecutionTerminal;
			break;
		case 'messageBlock':
			_messageBlockExecutionTerminal = ensureTerminal(terminalName, _messageBlockExecutionTerminal);
			targetTerminal = _messageBlockExecutionTerminal;
			break;
		default:
			vscode.window.showErrorMessage(`Unknown terminal type: ${terminalType}`);
			return;
	}
	targetTerminal.show(true);
	targetTerminal.sendText(command);
}

async function executeDocumentCommand(initialDocumentUri: vscode.Uri) {
	const finalDocumentUri = await saveDocumentBeforeExecution(initialDocumentUri);
	if (!finalDocumentUri) {
		return;
	}

	const filePath = finalDocumentUri.fsPath;
	const config = vscode.workspace.getConfiguration('Domarkx');
	const commandTemplate = config.get<string>('executionCommand');

	if (!commandTemplate) {
		vscode.window.showErrorMessage("Document execution command (Domarkx.executionCommand) is not configured in settings.");
		return;
	}

	const finalCommand = commandTemplate.replace(/\$\{file\}/g, `"${filePath}"`);
	await executeCommandInSpecificTerminal(finalCommand, "Domarkx Execution", 'document');
}

async function executeCodeBlockInTerminal(args: ExecuteCodeBlockCommandArgs) {
	const { uri, startLine, language, messageIndex, codeBlockInMessageIndex, commandTemplate } = args;

	const finalDocumentUri = await saveDocumentBeforeExecution(uri);
	if (!finalDocumentUri) {
		return;
	}

	if (!commandTemplate || commandTemplate.trim() === "") {
		vscode.window.showErrorMessage("Code Block execution command is not valid. Please check your settings.");
		return;
	}

	const filePath = finalDocumentUri.fsPath;
	const finalCommand = commandTemplate
		.replace(/\$\{file\}/g, `"${filePath}"`)
		.replace(/\$\{lineNumber\}/g, startLine.toString())
		.replace(/\$\{language\}/g, language || "")
		.replace(/\$\{messageIndex\}/g, messageIndex.toString())
		.replace(/\$\{codeBlockInMessageIndex\}/g, codeBlockInMessageIndex.toString());

	await executeCommandInSpecificTerminal(finalCommand, "LLM Code Block Execution", 'codeBlock');
}

async function executeMessageBlockInTerminal(args: ExecuteMessageBlockCommandArgs) {
	const { uri, messageIndex, commandTemplate, speakerName, speakerText, messageContentStartLine, messageContentEndLine } = args;

	const finalDocumentUri = await saveDocumentBeforeExecution(uri);
	if (!finalDocumentUri) {
		return;
	}

	if (!commandTemplate || commandTemplate.trim() === "") {
		vscode.window.showErrorMessage("Message Block execution command is not valid. Please check your settings.");
		return;
	}

	const filePath = finalDocumentUri.fsPath;
	let messageContent = '';
	if (messageContentStartLine !== undefined && messageContentEndLine !== undefined) {
		const document = await vscode.workspace.openTextDocument(finalDocumentUri);
		const lines = document.getText().split(/\r\n|\r|\n/);
		const start = Math.max(0, messageContentStartLine);
		const end = Math.min(lines.length, messageContentEndLine);

		for (let i = start; i < end; i++) {
			messageContent += lines[i] + '\n';
		}
		messageContent = messageContent.trimEnd();
	}


	const finalCommand = commandTemplate
		.replace(/\$\{file\}/g, `"${filePath}"`)
		.replace(/\$\{messageIndex\}/g, messageIndex.toString())
		.replace(/\$\{messageSpeaker\}/g, JSON.stringify(speakerName))
		.replace(/\$\{messageSpeakerText\}/g, JSON.stringify(speakerText))
		.replace(/\$\{messageContent\}/g, JSON.stringify(messageContent))
		.replace(/\$\{messageContentBase64\}/g, Buffer.from(messageContent, 'utf8').toString('base64'));

	await executeCommandInSpecificTerminal(finalCommand, "Message Block Execution", 'messageBlock');
}

export function deactivate() {
	console.log('Domarkx Tools extension is now deactivated.');
	if (_documentExecutionTerminal) {
		_documentExecutionTerminal.dispose();
		_documentExecutionTerminal = undefined;
	}
	if (_codeBlockExecutionTerminal) {
		_codeBlockExecutionTerminal.dispose();
		_codeBlockExecutionTerminal = undefined;
	}
	if (_messageBlockExecutionTerminal) {
		_messageBlockExecutionTerminal.dispose();
		_messageBlockExecutionTerminal = undefined;
	}
	_context = undefined;
}