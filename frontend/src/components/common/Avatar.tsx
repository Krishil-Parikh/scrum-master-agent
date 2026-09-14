interface AvatarProps {
  name: string;
  color?: string;
  size?: number;
}

export function Avatar({ name, color, size = 32 }: AvatarProps) {
  return (
    <span
      className="avatar"
      style={{
        width: size,
        height: size,
        fontSize: Math.max(10, size * 0.4),
        background: color ?? "#495057",
      }}
    >
      {name}
    </span>
  );
}
