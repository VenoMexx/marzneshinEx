import {
    FormControl,
    FormField,
    FormItem,
    FormLabel,
    FormMessage,
    FormDescription,
    Input,
    HoverCard,
    HoverCardTrigger,
    HoverCardContent,
} from "@marzneshin/common/components";
import { useFormContext } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { InfoCircledIcon } from "@radix-ui/react-icons";

export const WeightField = () => {
    const { t } = useTranslation()
    const form = useFormContext()
    return (
        <FormField
            control={form.control}
            name="weight"
            render={({ field }) => (
                <FormItem className="w-1/3">
                    <FormLabel className="flex items-center gap-1">
                        {t('weight')}
                        <HoverCard>
                            <HoverCardTrigger asChild>
                                <InfoCircledIcon className="h-3 w-3 text-muted-foreground cursor-help" />
                            </HoverCardTrigger>
                            <HoverCardContent className="w-80">
                                <div className="space-y-2">
                                    <h4 className="text-sm font-semibold">
                                        {t('page.hosts.weight.tooltip.title')}
                                    </h4>
                                    <p className="text-xs text-muted-foreground">
                                        {t('page.hosts.weight.tooltip.description')}
                                    </p>
                                    <div className="text-xs">
                                        <strong>{t('page.hosts.weight.tooltip.examples')}:</strong>
                                        <ul className="list-disc list-inside mt-1 space-y-1 text-muted-foreground">
                                            <li>10+ → {t('page.hosts.weight.tooltip.high')}</li>
                                            <li>5-9 → {t('page.hosts.weight.tooltip.medium')}</li>
                                            <li>1-4 → {t('page.hosts.weight.tooltip.low')}</li>
                                        </ul>
                                    </div>
                                </div>
                            </HoverCardContent>
                        </HoverCard>
                    </FormLabel>
                    <FormControl>
                        <Input
                            type="number"
                            min={1}
                            max={100}
                            placeholder="1"
                            {...field}
                        />
                    </FormControl>
                    <FormDescription className="text-xs">
                        {t('page.hosts.weight.description')}
                    </FormDescription>
                    <FormMessage />
                </FormItem>
            )}
        />
    )
}
