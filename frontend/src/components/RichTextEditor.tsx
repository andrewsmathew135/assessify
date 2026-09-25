import Underline from "@tiptap/extension-underline";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, type ReactNode } from "react";

interface RichTextEditorProps {
  value: string;
  onChange: (html: string) => void;
  ariaLabel?: string;
  minHeight?: string;
}

function ToolbarButton({
  action,
  isActive,
  label,
  children,
}: {
  action: () => void;
  isActive: boolean;
  label: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={action}
      aria-label={label}
      aria-pressed={isActive}
      title={label}
      className={`flex h-8 w-8 items-center justify-center rounded-md text-sm transition-colors ${
        isActive ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-200"
      }`}
    >
      {children}
    </button>
  );
}

export function RichTextEditor({ value, onChange, ariaLabel, minHeight = "7rem" }: RichTextEditorProps) {
  const editor = useEditor({
    extensions: [StarterKit, Underline],
    content: value,
    editorProps: {
      attributes: {
        class: "prose prose-sm max-w-none px-4 py-3 focus:outline-none",
        style: `min-height: ${minHeight}`,
        "aria-label": ariaLabel ?? "Rich text editor",
        role: "textbox",
        "aria-multiline": "true",
      },
    },
    onUpdate: ({ editor }) => onChange(editor.getHTML()),
  });

  // Keep the editor in sync if the value is reset externally (e.g. cleared).
  useEffect(() => {
    if (editor && value !== editor.getHTML()) {
      editor.commands.setContent(value, false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  if (!editor) return null;

  return (
    <div className="overflow-hidden rounded-lg border border-slate-300 focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-200">
      <div className="flex items-center gap-1 border-b border-slate-200 bg-slate-50 px-2 py-1">
        <ToolbarButton
          label="Bold"
          isActive={editor.isActive("bold")}
          action={() => editor.chain().focus().toggleBold().run()}
        >
          <span className="font-bold">B</span>
        </ToolbarButton>
        <ToolbarButton
          label="Italic"
          isActive={editor.isActive("italic")}
          action={() => editor.chain().focus().toggleItalic().run()}
        >
          <span className="italic">I</span>
        </ToolbarButton>
        <ToolbarButton
          label="Underline"
          isActive={editor.isActive("underline")}
          action={() => editor.chain().focus().toggleUnderline().run()}
        >
          <span className="underline">U</span>
        </ToolbarButton>
        <span className="mx-1 h-5 w-px bg-slate-200" />
        <ToolbarButton
          label="Bullet list"
          isActive={editor.isActive("bulletList")}
          action={() => editor.chain().focus().toggleBulletList().run()}
        >
          •
        </ToolbarButton>
        <ToolbarButton
          label="Numbered list"
          isActive={editor.isActive("orderedList")}
          action={() => editor.chain().focus().toggleOrderedList().run()}
        >
          1.
        </ToolbarButton>
      </div>
      <EditorContent editor={editor} />
    </div>
  );
}
